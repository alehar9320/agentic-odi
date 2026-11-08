import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DRAIN_LOCK_NAME, drainOutbox } from "./outbox";
import { MemoryLocalStore } from "./store/memoryStore";
import type { OutboxRecord } from "./store/types";

function record(overrides: Partial<OutboxRecord> = {}): OutboxRecord {
  return {
    id: "rec",
    kind: "create",
    entity: "job",
    local_id: null,
    server_id: null,
    payload: {},
    depends_on: [],
    state: "pending",
    attempts: 0,
    last_error: null,
    created_at: "2026-01-01T00:00:00.000Z",
    acknowledged_at: null,
    ...overrides,
  };
}

/** A LockManager that grants `ifAvailable` requests and refuses otherwise. */
class FakeLockManager {
  readonly held = new Set<string>();
  readonly names: string[] = [];

  async request(
    name: string,
    optionsOrCallback: LockOptions | ((lock: Lock | null) => unknown),
    maybeCallback?: (lock: Lock | null) => unknown,
  ): Promise<unknown> {
    const options = typeof optionsOrCallback === "function" ? {} : optionsOrCallback;
    const callback =
      typeof optionsOrCallback === "function" ? optionsOrCallback : maybeCallback;
    this.names.push(name);
    if (this.held.has(name)) {
      if (options.ifAvailable) {
        return callback?.(null);
      }
      throw new Error("this fake never queues a blocking request");
    }
    this.held.add(name);
    try {
      return await callback?.({ name } as Lock);
    } finally {
      this.held.delete(name);
    }
  }
}

function stubLocks(manager: FakeLockManager): void {
  Object.defineProperty(navigator, "locks", {
    value: manager,
    configurable: true,
    writable: true,
  });
}

function removeLocks(): void {
  delete (navigator as unknown as { locks?: unknown }).locks;
}

beforeEach(() => {
  removeLocks();
});

afterEach(() => {
  removeLocks();
  vi.useRealTimers();
});

describe("drainOutbox with navigator.locks", () => {
  it("sends each record once when two drains race", async () => {
    const locks = new FakeLockManager();
    stubLocks(locks);
    const store = new MemoryLocalStore();
    await store.enqueueOutbox(record({ id: "a" }));
    await store.enqueueOutbox(record({ id: "b" }));

    const sent: string[] = [];
    const send = (entry: OutboxRecord) => {
      sent.push(entry.id);
    };

    const [first, second] = await Promise.all([
      drainOutbox({ store, send }),
      drainOutbox({ store, send }),
    ]);

    expect(sent.sort()).toEqual(["a", "b"]);
    expect(first.ran).toBe(true);
    expect(second.ran).toBe(false);
    expect(second.reason).toBe("locked");
    // Both drains ask for the same origin-wide lock; only one is granted.
    expect(locks.names).toEqual([DRAIN_LOCK_NAME, DRAIN_LOCK_NAME]);
    // Only one mechanism runs: the lock, never the lease.
    expect(await store.getDrainLease()).toBeNull();
  });

  it("falls back to the lease when the lock manager refuses", async () => {
    const refusing = {
      request: () => Promise.reject(new Error("locks unavailable")),
    } as unknown as LockManager;
    const store = new MemoryLocalStore();
    await store.enqueueOutbox(record({ id: "a" }));

    const sent: string[] = [];
    const outcome = await drainOutbox({
      store,
      send: (entry) => {
        sent.push(entry.id);
      },
      locks: refusing,
    });

    expect(sent).toEqual(["a"]);
    expect(outcome.ran).toBe(true);
    // The lease is released once the drain finishes.
    expect(await store.getDrainLease()).toBeNull();
  });
});

describe("drainOutbox resuming after the holder closes", () => {
  it("lets the next drain pick up records the first left pending", async () => {
    const store = new MemoryLocalStore();
    await store.enqueueOutbox(record({ id: "a" }));
    const sent: string[] = [];

    // The first drain sends "a" and releases the lease.
    await drainOutbox({ store, send: (entry) => void sent.push(entry.id) });
    expect(sent).toEqual(["a"]);

    // A record queued afterwards is drained by the next trigger.
    await store.enqueueOutbox(record({ id: "b", created_at: "2026-01-01T00:00:01.000Z" }));
    const second = await drainOutbox({
      store,
      send: (entry) => void sent.push(entry.id),
    });
    expect(sent).toEqual(["a", "b"]);
    expect(second.ran).toBe(true);
  });
});

describe("drainOutbox without navigator.locks", () => {
  it("sends each record once when two drains race", async () => {
    expect((navigator as unknown as { locks?: unknown }).locks).toBeUndefined();
    const store = new MemoryLocalStore();
    await store.enqueueOutbox(record({ id: "a" }));
    await store.enqueueOutbox(record({ id: "b" }));

    const sent: string[] = [];
    const send = (entry: OutboxRecord) => {
      sent.push(entry.id);
    };

    const [first, second] = await Promise.all([
      drainOutbox({ store, send }),
      drainOutbox({ store, send }),
    ]);

    expect(sent.sort()).toEqual(["a", "b"]);
    expect(first.ran).toBe(true);
    expect(second.ran).toBe(false);
    expect(second.reason).toBe("lease-held");
    // The winner releases the lease when it finishes.
    expect(await store.getDrainLease()).toBeNull();
  });

  it("reclaims a crashed holder's lease after it expires", async () => {
    const store = new MemoryLocalStore();
    await store.enqueueOutbox(record({ id: "a" }));
    const ttl = 1_000;
    // A drain that crashed left its lease behind.
    await store.claimDrainLease("ghost", 10_000, ttl);

    const sent: string[] = [];
    const send = (entry: OutboxRecord) => {
      sent.push(entry.id);
    };

    // Before expiry the stale lease still holds the queue back.
    const blocked = await drainOutbox({ store, send, now: () => 10_500 });
    expect(blocked.ran).toBe(false);
    expect(blocked.reason).toBe("lease-held");
    expect(sent).toEqual([]);

    // Past expiry the next drain reclaims it and drains.
    const reclaimed = await drainOutbox({
      store,
      send,
      now: () => 10_000 + ttl + 1,
    });
    expect(reclaimed.ran).toBe(true);
    expect(sent).toEqual(["a"]);
  });

  it("renews the lease while the drain runs", async () => {
    vi.useFakeTimers();
    const store = new MemoryLocalStore();
    await store.enqueueOutbox(record({ id: "a" }));

    let release: () => void = () => undefined;
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    let clock = 1_000;
    const running = drainOutbox({
      store,
      send: () => gate,
      holder: "h",
      leaseTtlMs: 100,
      now: () => clock,
    });

    await vi.advanceTimersByTimeAsync(0);
    expect((await store.getDrainLease())?.holder).toBe("h");

    // Move past the original expiry; the renewal keeps the claim alive.
    clock = 1_100;
    await vi.advanceTimersByTimeAsync(60);
    const renewed = await store.getDrainLease();
    expect(renewed?.holder).toBe("h");
    expect(renewed?.expires_at).toBe(1_200);

    release();
    await running;
    expect(await store.getDrainLease()).toBeNull();
  });
});

describe("drain lease ownership", () => {
  it("only renews and releases the lease a holder owns", async () => {
    const store = new MemoryLocalStore();
    expect(await store.claimDrainLease("a", 0, 1_000)).toBeNull();

    expect(await store.renewDrainLease("b", 10, 1_000)).toBe(false);
    expect(await store.releaseDrainLease("b")).toBe(false);

    expect(await store.renewDrainLease("a", 10, 1_000)).toBe(true);
    expect(await store.getDrainLease()).toEqual({ holder: "a", expires_at: 1_010 });

    expect(await store.releaseDrainLease("a")).toBe(true);
    expect(await store.getDrainLease()).toBeNull();
  });

  it("lets the same holder re-claim its own lease without contention", async () => {
    const store = new MemoryLocalStore();
    expect(await store.claimDrainLease("a", 0, 1_000)).toBeNull();
    expect(await store.claimDrainLease("a", 10, 1_000)).toBeNull();
  });
});
