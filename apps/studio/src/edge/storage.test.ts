import { afterEach, describe, expect, it } from "vitest";

import "fake-indexeddb/auto";

import { EdgeStateStore, withEngineLock } from "./storage";

async function clearDb() {
  await indexedDB.deleteDatabase("agentic-odi-edge");
}

afterEach(async () => {
  await clearDb();
});

describe("EdgeStateStore", () => {
  it("starts every tier empty and consent unset", async () => {
    const store = await EdgeStateStore.open();
    expect(await store.getTierStates()).toEqual({
      t1: { status: "empty", cachedAt: null },
      t2: { status: "empty", cachedAt: null },
      t3: { status: "empty", cachedAt: null },
    });
    expect(await store.getConsent()).toBe("unset");
    expect(await store.getUsage()).toEqual({ edgeTurns: 0, streamedSeconds: 0 });
    store.close();
  });

  it("persists tier state, usage, and consent across instances", async () => {
    const store = await EdgeStateStore.open();
    await store.setTierState("t1", { status: "cached", cachedAt: "2026-11-01T00:00:00Z" });
    await store.recordEdgeTurn(45);
    await store.setConsent("granted");
    store.close();

    const next = await EdgeStateStore.open();
    expect((await next.getTierStates()).t1.status).toBe("cached");
    expect(await next.getUsage()).toEqual({ edgeTurns: 1, streamedSeconds: 45 });
    expect(await next.getConsent()).toBe("granted");
    next.close();
  });

  it("accumulates usage across turns and ignores negative durations", async () => {
    const store = await EdgeStateStore.open();
    await store.recordEdgeTurn(10);
    await store.recordEdgeTurn(-3);
    await store.recordEdgeTurn(2.5);
    expect(await store.getUsage()).toEqual({ edgeTurns: 3, streamedSeconds: 12.5 });
    store.close();
  });

  it("forgets everything on reset", async () => {
    const store = await EdgeStateStore.open();
    await store.setTierState("t2", { status: "active", cachedAt: "now" });
    await store.recordEdgeTurn(1);
    await store.setConsent("denied");
    await store.reset();
    expect((await store.getTierStates()).t2.status).toBe("empty");
    expect(await store.getUsage()).toEqual({ edgeTurns: 0, streamedSeconds: 0 });
    expect(await store.getConsent()).toBe("unset");
    store.close();
  });
});

describe("withEngineLock", () => {
  it("falls back to a page mutex when navigator.locks is missing", async () => {
    const order: string[] = [];
    const slow = withEngineLock(async () => {
      order.push("first-start");
      await new Promise((resolve) => setTimeout(resolve, 10));
      order.push("first-end");
      return "a";
    });
    order.push("second-start");
    const blocked = await withEngineLock(async () => "b");
    const first = await slow;

    expect(first).toEqual({ acquired: true, value: "a" });
    expect(blocked).toEqual({ acquired: false, value: null });
    expect(order).toEqual(["first-start", "second-start", "first-end"]);
  });

  it("honours a browser lock manager that reports the lock busy", async () => {
    Object.defineProperty(navigator, "locks", {
      configurable: true,
      value: {
        request: async (_name: string, _opts: unknown, task: (lock: unknown) => unknown) =>
          task(null),
      },
    });
    try {
      const outcome = await withEngineLock(async () => "value");
      expect(outcome).toEqual({ acquired: false, value: null });
    } finally {
      delete (navigator as unknown as Record<string, unknown>).locks;
    }
  });
});
