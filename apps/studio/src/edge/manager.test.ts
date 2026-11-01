import { beforeEach, describe, expect, it, vi } from "vitest";

import "fake-indexeddb/auto";

import type { RawSseEvent } from "../api/sse";
import type { ChatStreamRequest, StudioConfig } from "../types";
import { EDGE_TIERS, computeEligibility, tierById } from "./ladder";
import type { SchedulerEnvironment } from "./scheduler";
import { EdgeStateStore } from "./storage";
import { EdgeManager, hasRemoteEndpoint, shouldUseEdge } from "./manager";
import { FakeEdgeEngine } from "../test/edgeFake";
import type { Eligibility } from "./types";

const healthyDesktop: Eligibility = computeEligibility({
  webgpu: true,
  shaderF16: true,
  vramGB: null,
  deviceMemoryGB: 16,
  freeStorageBytes: 40_000_000_000,
  saveData: false,
});

const noWebGPU: Eligibility = computeEligibility({
  webgpu: false,
  shaderF16: false,
  vramGB: null,
  deviceMemoryGB: 16,
  freeStorageBytes: 40_000_000_000,
  saveData: false,
});

function idleQueue(): { env: SchedulerEnvironment; queue: Array<() => void> } {
  const queue: Array<() => void> = [];
  return {
    queue,
    env: {
      requestIdle(callback) {
        queue.push(callback);
        return () => {
          const index = queue.indexOf(callback);
          if (index >= 0) {
            queue.splice(index, 1);
          }
        };
      },
      visible: () => true,
      saveData: () => false,
    },
  };
}

const noEndpoint: StudioConfig = {
  base_url: "http://localhost:8001/v1",
  api_key: "",
  model_name: "",
  mcp_url: "http://localhost:9000/mcp",
};

const baseRequest: ChatStreamRequest = {
  base_url: "",
  api_key: "",
  model: "",
  mcp_url: "",
  messages: [{ id: "m-0", parentId: null, role: "user", content: "hi" }],
  brief: null,
};

function decision(overrides: Partial<Parameters<typeof shouldUseEdge>[0]> = {}) {
  return shouldUseEdge({
    flagEnabled: true,
    endpointConfigured: false,
    llmHealthy: false,
    consent: "granted",
    servedTier: "t1",
    ...overrides,
  });
}

describe("shouldUseEdge", () => {
  it("serves on the edge only for a keyless, unhealthy, consented device with a cached tier", () => {
    expect(decision()).toBe(true);
  });

  it("every gate that fails turns the edge off", () => {
    expect(decision({ flagEnabled: false })).toBe(false);
    expect(decision({ endpointConfigured: true })).toBe(false);
    expect(decision({ llmHealthy: true })).toBe(false);
    expect(decision({ consent: "unset" })).toBe(false);
    expect(decision({ consent: "denied" })).toBe(false);
    expect(decision({ servedTier: null })).toBe(false);
  });
});

describe("hasRemoteEndpoint", () => {
  it("needs url, key and model together, and never counts the local sidecar", () => {
    expect(hasRemoteEndpoint(noEndpoint)).toBe(false);
    expect(hasRemoteEndpoint({ ...noEndpoint, api_key: "sk", model_name: "gpt" })).toBe(false);
    expect(
      hasRemoteEndpoint({
        ...noEndpoint,
        base_url: "https://api.openai.com/v1",
        api_key: "sk",
        model_name: "gpt",
      }),
    ).toBe(true);
  });
});

describe("EdgeManager", () => {
  async function prime(options: {
    consent?: "unset" | "granted" | "denied";
    cachedTiers?: string[];
  }) {
    const store = await EdgeStateStore.open();
    await store.reset();
    if (options.consent) {
      await store.setConsent(options.consent);
    }
    for (const id of options.cachedTiers ?? []) {
      await store.setTierState(id as "t1" | "t2" | "t3", {
        status: "cached",
        cachedAt: "2026-01-01T00:00:00.000Z",
      });
    }
    store.close();
  }

  let manager: EdgeManager;
  let engine: FakeEdgeEngine;

  beforeEach(async () => {
    window.localStorage.clear();
    manager = new EdgeManager();
    manager.reset();
    engine = new FakeEdgeEngine();
    manager.setEngineFactory(async () => engine);
    await prime({ consent: "granted", cachedTiers: ["t1"] });
  });

  it("prefers the strongest cached tier", async () => {
    await prime({ consent: "granted", cachedTiers: ["t1", "t3"] });
    expect(await manager.servedTier()).toBe("t3");
    await prime({ consent: "granted", cachedTiers: ["t1", "t2"] });
    expect(await manager.servedTier()).toBe("t2");
  });

  it("reports it cannot serve before consent, or with nothing cached", async () => {
    expect(await manager.canServe(noEndpoint, false)).toBe(true);
    await prime({ consent: "denied", cachedTiers: ["t1"] });
    expect(await manager.canServe(noEndpoint, false)).toBe(false);
    await prime({ consent: "granted", cachedTiers: [] });
    expect(await manager.canServe(noEndpoint, false)).toBe(false);
    expect(await manager.canServe(noEndpoint, true)).toBe(false);
  });

  it("loads the cached model once, streams frames, and records the answered turn", async () => {
    const events: RawSseEvent[] = [];
    await manager.stream(baseRequest, (event) => events.push(event));
    await manager.stream(baseRequest, (event) => events.push(event));

    expect(engine.loads).toEqual([tierById("t1").modelId]);
    expect(events.filter((event) => event.event === "message")).toHaveLength(2);
    expect(events.map((event) => event.event)).toContain("delta");

    const store = await EdgeStateStore.open();
    expect((await store.getUsage()).edgeTurns).toBe(2);
    expect((await store.getTierStates()).t1.status).toBe("active");
    store.close();
  });

  it("does not credit a turn that failed mid-stream", async () => {
    manager.setEngineFactory(async () => new FakeEdgeEngine({ failWith: new Error("device lost") }));
    const events: RawSseEvent[] = [];
    await manager.stream(baseRequest, (event) => events.push(event));

    expect(events.map((event) => event.event)).toEqual(["status", "error"]);
    const store = await EdgeStateStore.open();
    expect((await store.getUsage()).edgeTurns).toBe(0);
    store.close();
  });

  it("refuses to stream with nothing cached, rather than downloading silently", async () => {
    await prime({ consent: "granted", cachedTiers: [] });
    await expect(manager.stream(baseRequest, () => {})).rejects.toThrow(/no cached tier/);
  });

  it("switches engines when the ladder moves the served tier up", async () => {
    await manager.stream(baseRequest, () => {});
    const before = engine.loads.length;
    await prime({ consent: "granted", cachedTiers: ["t1", "t2"] });
    await manager.stream(baseRequest, () => {});
    expect(before).toBe(1);
    expect(engine.loads).toEqual([
      EDGE_TIERS[0].modelId,
      EDGE_TIERS[1].modelId,
    ]);
  });

  it("ten served turns earn the next tier: it prefetches in background, then answers on it", async () => {
    const { env, queue } = idleQueue();
    manager.setSchedulerEnvironment(env);
    manager.setEligibilityFactory(async () => healthyDesktop);
    const notices: string[] = [];
    manager.setListener((notice) =>
      notices.push(notice.kind === "consent-changed" ? notice.kind : `${notice.kind}:${notice.tier}`),
    );

    for (let turn = 0; turn < 10; turn += 1) {
      await manager.stream(baseRequest, () => {});
    }
    // Nine turns earned nothing; the tenth queues a prefetch but nothing is
    // fetched until the device is idle.
    await vi.waitFor(() => expect(queue).toHaveLength(1));
    expect(engine.loads).toEqual([EDGE_TIERS[0].modelId]);
    queue.shift()?.();
    await vi.waitFor(() => expect(notices).toContain("unlocked:t2"));

    const store = await EdgeStateStore.open();
    expect((await store.getTierStates()).t2.status).toBe("active");
    store.close();

    await manager.stream(baseRequest, () => {});
    expect(engine.loads).toEqual([EDGE_TIERS[0].modelId, EDGE_TIERS[1].modelId]);
    manager.setListener(null);
  });

  describe("the one-time offer", () => {
    beforeEach(async () => {
      await prime({ consent: "unset", cachedTiers: [] });
      manager.setEligibilityFactory(async () => healthyDesktop);
    });

    it("names the entry tier and its size when a keyless device has never been asked", async () => {
      const offer = await manager.offerFor(noEndpoint, false);
      expect(offer).not.toBeNull();
      expect(offer?.tier).toBe("t1");
      expect(offer?.approxBytes).toBe(EDGE_TIERS[0].approxBytes);
      expect(offer?.label).toBe(EDGE_TIERS[0].label);
    });

    it("stays quiet when the browser cannot host a model at all", async () => {
      manager.setEligibilityFactory(async () => noWebGPU);
      expect(await manager.offerFor(noEndpoint, false)).toBeNull();
    });

    it("stays quiet when a paid endpoint answers, or a tier is already cached", async () => {
      expect(await manager.offerFor(noEndpoint, true)).toBeNull();
      expect(
        await manager.offerFor({ ...noEndpoint, base_url: "https://api.openai.com/v1", api_key: "sk", model_name: "gpt" }, false),
      ).toBeNull();
      await prime({ consent: "unset", cachedTiers: ["t1"] });
      expect(await manager.offerFor(noEndpoint, false)).toBeNull();
    });

    it("asks once: an answer either way retires the offer", async () => {
      await manager.decline();
      expect(await manager.offerFor(noEndpoint, false)).toBeNull();
      await prime({ consent: "granted", cachedTiers: [] });
      expect(await manager.offerFor(noEndpoint, false)).toBeNull();
    });
  });

  describe("grantAndStart", () => {
    beforeEach(async () => {
      await prime({ consent: "unset", cachedTiers: [] });
      manager.setEligibilityFactory(async () => healthyDesktop);
    });

    it("consents, fetches the entry tier in a quiet moment, and is then ready to serve", async () => {
      const { env, queue } = idleQueue();
      manager.setSchedulerEnvironment(env);
      const notices: string[] = [];
      manager.setListener((notice) =>
        notices.push(notice.kind === "consent-changed" ? notice.kind : `${notice.kind}:${notice.tier}`),
      );

      const started = manager.grantAndStart();
      await vi.waitFor(() => expect(queue).toHaveLength(1));
      expect(engine.loads).toEqual([]);
      queue.shift()?.();
      expect(await started).toBe("t1");

      expect(notices).toContain("consent-changed");
      expect(notices).toContain("downloading:t1");
      expect(notices).toContain("ready:t1");
      expect(engine.loads).toEqual([EDGE_TIERS[0].modelId]);
      expect(await manager.servedTier()).toBe("t1");
      expect(await manager.canServe(noEndpoint, false)).toBe(true);

      const store = await EdgeStateStore.open();
      expect(await store.getConsent()).toBe("granted");
      expect((await store.getTierStates()).t1.status).toBe("active");
      store.close();
      manager.setListener(null);
    });

    it("records a refusal so nothing is downloaded and nothing is asked again", async () => {
      await manager.decline();
      const store = await EdgeStateStore.open();
      expect(await store.getConsent()).toBe("denied");
      store.close();
      expect(engine.loads).toEqual([]);
      expect(await manager.canServe(noEndpoint, false)).toBe(false);
    });
  });
});
