import { beforeEach, describe, expect, it, vi } from "vitest";

import "fake-indexeddb/auto";

import { EDGE_TIERS, computeEligibility } from "./ladder";
import { EdgeStateStore } from "./storage";
import { EdgeScheduler, type SchedulerEnvironment } from "./scheduler";
import { FakeEdgeEngine } from "../test/edgeFake";
import type { Eligibility, LoadProgress } from "./types";

const healthyDesktop: Eligibility = computeEligibility({
  webgpu: true,
  shaderF16: true,
  vramGB: null,
  deviceMemoryGB: 16,
  freeStorageBytes: 40_000_000_000,
  saveData: false,
});

const twoGigabyteDevice: Eligibility = computeEligibility({
  webgpu: true,
  shaderF16: true,
  vramGB: null,
  deviceMemoryGB: 2,
  freeStorageBytes: 40_000_000_000,
  saveData: false,
});

function fakeEnv() {
  const queue: Array<() => void> = [];
  const moment = { visible: true, saveData: false };
  const env: SchedulerEnvironment = {
    requestIdle(callback) {
      queue.push(callback);
      return () => {
        const index = queue.indexOf(callback);
        if (index >= 0) {
          queue.splice(index, 1);
        }
      };
    },
    visible: () => moment.visible,
    saveData: () => moment.saveData,
  };
  return {
    env,
    moment,
    queue,
    async fireIdle() {
      await vi.waitFor(() => expect(queue).toHaveLength(1));
      queue.shift()?.();
    },
  };
}

async function prime(options: {
  turns?: number;
  streamedSeconds?: number;
  consent?: "granted" | "denied" | "unset";
  hosted?: Array<[id: "t1" | "t2" | "t3", status: "cached" | "active"]>;
}) {
  const store = await EdgeStateStore.open();
  await store.reset();
  if (options.consent === "granted") {
    await store.setConsent("granted");
  } else if (options.consent) {
    await store.setConsent(options.consent);
  }
  for (const [id, status] of options.hosted ?? [["t1", "active"]]) {
    await store.setTierState(id, { status, cachedAt: "2026-01-01T00:00:00.000Z" });
  }
  for (let index = 0; index < (options.turns ?? 0); index += 1) {
    await store.recordEdgeTurn(1);
  }
  if (options.streamedSeconds) {
    await store.recordEdgeTurn(options.streamedSeconds);
  }
  store.close();
}

function harness(overrides: { eligibility?: Eligibility; locks?: boolean } = {}) {
  const harnessEnv = fakeEnv();
  const engine = new FakeEdgeEngine();
  const unlocked: string[] = [];
  const progress: Array<[string, LoadProgress]> = [];
  let lockRequest: ReturnType<typeof vi.fn> | null = null;
  if (overrides.locks) {
    // Another tab owns the engine: `ifAvailable` resolves with no lock.
    lockRequest = vi.fn(
      async (
        _name: string,
        _options: unknown,
        callback: (lock: unknown) => Promise<unknown>,
      ) => callback(null),
    );
    Object.defineProperty(navigator, "locks", {
      value: { request: lockRequest },
      configurable: true,
    });
  }
  const scheduler = new EdgeScheduler({
    state: {
      getTierStates: () => EdgeStateStore.open().then((s) => s.getTierStates()),
      setTierState: (id, state) => EdgeStateStore.open().then((s) => s.setTierState(id, state)),
      getUsage: () => EdgeStateStore.open().then((s) => s.getUsage()),
      recordEdgeTurn: (seconds) => EdgeStateStore.open().then((s) => s.recordEdgeTurn(seconds)),
      getConsent: () => EdgeStateStore.open().then((s) => s.getConsent()),
      setConsent: (state) => EdgeStateStore.open().then((s) => s.setConsent(state)),
      reset: () => EdgeStateStore.open().then((s) => s.reset()),
    },
    engine: async () => engine,
    eligibility: async () => overrides.eligibility ?? healthyDesktop,
    onProgress: (tier, p) => progress.push([tier, p]),
    onUnlocked: (tier) => unlocked.push(tier),
    env: harnessEnv.env,
  });
  return {
    scheduler,
    engine,
    unlocked,
    progress,
    lockRequest,
    ...harnessEnv,
    cleanup() {
      if (lockRequest) {
        Reflect.deleteProperty(navigator, "locks");
      }
    },
  };
}

beforeEach(async () => {
  await prime({ consent: "granted", hosted: [["t1", "active"]], turns: 9 });
});

describe("EdgeScheduler", () => {
  it("waits for the tenth served turn before reaching for the next tier", async () => {
    const h = harness();
    expect(await h.scheduler.noteTurn()).toBeNull();
    expect(h.queue).toHaveLength(0);

    await prime({ consent: "granted", hosted: [["t1", "active"]], turns: 10 });
    const started = h.scheduler.noteTurn();
    await vi.waitFor(() => expect(h.queue).toHaveLength(1));
    // Nothing has been fetched until the device is actually idle.
    expect(h.engine.loads).toEqual([]);
    h.queue.shift()?.();

    expect(await started).toBe("t2");
    expect(h.engine.loads).toEqual([EDGE_TIERS[1].modelId]);
    expect(h.unlocked).toEqual(["t2"]);
    const store = await EdgeStateStore.open();
    expect((await store.getTierStates()).t2.status).toBe("active");
    store.close();
    h.cleanup();
  });

  it("treats a quarter-hour of streamed answers as equally earned", async () => {
    await prime({ consent: "granted", hosted: [["t1", "active"]], streamedSeconds: 900 });
    const h = harness();
    const started = h.scheduler.noteTurn();
    await h.fireIdle();
    expect(await started).toBe("t2");
    h.cleanup();
  });

  it("never starts a download for a hidden tab or a Save Data connection", async () => {
    await prime({ consent: "granted", hosted: [["t1", "active"]], turns: 10 });
    const hidden = harness();
    hidden.moment.visible = false;
    expect(await hidden.scheduler.noteTurn()).toBeNull();
    expect(hidden.queue).toHaveLength(0);

    const saver = harness();
    saver.moment.saveData = true;
    expect(await saver.scheduler.noteTurn()).toBeNull();
    expect(saver.queue).toHaveLength(0);
    hidden.cleanup();
    saver.cleanup();
  });

  it("skips the download if the moment turned bad while queued", async () => {
    await prime({ consent: "granted", hosted: [["t1", "active"]], turns: 10 });
    const h = harness();
    const started = h.scheduler.noteTurn();
    await vi.waitFor(() => expect(h.queue).toHaveLength(1));
    h.moment.visible = false;
    h.queue.shift()?.();
    expect(await started).toBeNull();
    expect(h.engine.loads).toEqual([]);
    h.cleanup();
  });

  it("without a granted consent there is no prefetch, however much usage", async () => {
    await prime({ hosted: [["t1", "active"]], turns: 40 });
    const h = harness();
    expect(await h.scheduler.noteTurn()).toBeNull();
    await prime({ consent: "denied", hosted: [["t1", "active"]], turns: 40 });
    expect(await h.scheduler.noteTurn()).toBeNull();
    expect(h.queue).toHaveLength(0);
    h.cleanup();
  });

  it("tops out at the highest tier the device could host", async () => {
    await prime({ consent: "granted", hosted: [["t1", "active"]], turns: 10 });
    const small = harness({ eligibility: twoGigabyteDevice });
    expect(await small.scheduler.noteTurn()).toBeNull();

    await prime({ consent: "granted", hosted: [["t3", "active"]], turns: 10 });
    const top = harness();
    expect(await top.scheduler.noteTurn()).toBeNull();
    small.cleanup();
    top.cleanup();
  });

  it("climbs one rung: with t1 and t2 on disk it reaches for t3, never re-downloads", async () => {
    await prime({
      consent: "granted",
      hosted: [
        ["t1", "cached"],
        ["t2", "cached"],
      ],
      turns: 10,
    });
    const h = harness();
    const started = h.scheduler.noteTurn();
    await h.fireIdle();
    expect(await started).toBe("t3");
    expect(h.engine.loads).toEqual([EDGE_TIERS[2].modelId]);
    h.cleanup();
  });

  it("loses gracefully when another tab holds the engine lock", async () => {
    await prime({ consent: "granted", hosted: [["t1", "active"]], turns: 10 });
    const h = harness({ locks: true });
    const started = h.scheduler.noteTurn();
    await h.fireIdle();
    expect(await started).toBeNull();
    expect(h.lockRequest).toHaveBeenCalled();
    expect(h.engine.loads).toEqual([]);
    expect(h.unlocked).toEqual([]);
    h.cleanup();
  });

  it("stop() releases a queued prefetch instead of hanging it", async () => {
    await prime({ consent: "granted", hosted: [["t1", "active"]], turns: 10 });
    const h = harness();
    const started = h.scheduler.noteTurn();
    await vi.waitFor(() => expect(h.queue).toHaveLength(1));
    h.scheduler.stop();
    expect(await started).toBeNull();
    expect(h.queue).toHaveLength(0);
    h.cleanup();
  });

  it("reports download progress under the tier being fetched", async () => {
    await prime({ consent: "granted", hosted: [["t1", "active"]], turns: 10 });
    const h = harness();
    const started = h.scheduler.noteTurn();
    await h.fireIdle();
    await started;
    expect(h.progress.length).toBeGreaterThan(0);
    expect(h.progress.every(([tier]) => tier === "t2")).toBe(true);
    h.cleanup();
  });
});
