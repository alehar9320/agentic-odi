import { afterEach, describe, expect, it, vi } from "vitest";

import "fake-indexeddb/auto";

import { StorageFullError, isQuotaExceededError } from "../errors";
import { IndexedDbLocalStore } from "./indexedDbStore";
import { MemoryLocalStore } from "./memoryStore";
import { StorageWriteGuard } from "./storageFull";
import type { StoredJob } from "./types";

async function clearDb() {
  if (typeof indexedDB !== "undefined") {
    await indexedDB.deleteDatabase("agentic-odi-studio");
  }
}

afterEach(async () => {
  await clearDb();
});

function job(id: string): StoredJob {
  return {
    id,
    name: `Job ${id}`,
    description: "",
    seq: 1,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  };
}

/** Each shape a browser uses for the same full-disk condition. */
function quotaError(name: string, code?: number, message = "quota"): Error {
  const error = new Error(message);
  error.name = name;
  if (code !== undefined) {
    (error as Error & { code?: number }).code = code;
  }
  return error;
}

const QUOTA_SHAPES = [
  quotaError("QuotaExceededError", 22),
  quotaError("NS_ERROR_DOM_QUOTA_REACHED", 1014),
  quotaError("Error", undefined, "The quota has been exceeded."),
];

describe("isQuotaExceededError", () => {
  it("recognizes every browser shape and nothing else", () => {
    for (const shape of QUOTA_SHAPES) {
      expect(isQuotaExceededError(shape), shape.name).toBe(true);
    }
    expect(isQuotaExceededError(new Error("disk on fire"))).toBe(false);
    expect(isQuotaExceededError(undefined)).toBe(false);
    expect(isQuotaExceededError("QuotaExceededError")).toBe(false);
  });
});

describe("StorageWriteGuard", () => {
  it("translates each quota shape to one StorageFullError", async () => {
    for (const shape of QUOTA_SHAPES) {
      const guard = new StorageWriteGuard();
      await expect(
        guard.run(async () => {
          throw shape;
        }),
      ).rejects.toBeInstanceOf(StorageFullError);
    }
  });

  it("lets a non-quota failure through unchanged", async () => {
    const guard = new StorageWriteGuard();
    const failure = new Error("disk on fire");
    await expect(guard.run(async () => Promise.reject(failure))).rejects.toBe(failure);
    expect(guard.storageFull).toBe(false);
  });

  it("rejects a second write without running it, and tells subscribers once", async () => {
    const guard = new StorageWriteGuard();
    const listener = vi.fn();
    guard.subscribe(listener);
    const write = vi.fn(async () => {
      throw quotaError("QuotaExceededError", 22);
    });

    await expect(guard.run(write)).rejects.toBeInstanceOf(StorageFullError);
    expect(guard.storageFull).toBe(true);
    expect(listener).toHaveBeenCalledTimes(1);

    await expect(guard.run(write)).rejects.toBeInstanceOf(StorageFullError);
    expect(write).toHaveBeenCalledTimes(1);
    expect(listener).toHaveBeenCalledTimes(1);
  });
});

describe("IndexedDbLocalStore on a full disk", () => {
  it("pauses writes but keeps existing records readable", async () => {
    const store = await IndexedDbLocalStore.open();
    await store.putJob(job("j-1"));

    const db = (store as unknown as { db: { put: (store: string, value: unknown) => Promise<unknown> } })
      .db;
    const put = vi.spyOn(db, "put").mockRejectedValue(quotaError("QuotaExceededError", 22));

    await expect(store.putJob(job("j-2"))).rejects.toBeInstanceOf(StorageFullError);
    expect(store.storageFull).toBe(true);

    // The next write never reaches the database.
    await expect(store.putJob(job("j-3"))).rejects.toBeInstanceOf(StorageFullError);
    expect(put).toHaveBeenCalledTimes(1);

    // Reads are untouched: the work already stored is still there.
    const jobs = await store.listJobs();
    expect(jobs.map((entry) => entry.id)).toEqual(["j-1"]);

    put.mockRestore();
    store.close();
  });

  it("keeps the whole workspace exportable while writes are paused", async () => {
    const store = await IndexedDbLocalStore.open();
    await store.putJob(job("j-1"));

    const db = (store as unknown as { db: { put: (store: string, value: unknown) => Promise<unknown> } })
      .db;
    const put = vi.spyOn(db, "put").mockRejectedValue(quotaError("QuotaExceededError", 22));

    await expect(store.putJob(job("j-2"))).rejects.toBeInstanceOf(StorageFullError);

    const snapshot = await store.snapshot();
    expect(snapshot.jobs.map((entry) => entry.id)).toEqual(["j-1"]);

    put.mockRestore();
    store.close();
  });

  it("pauses the outbox too, so a queued retry cannot spin against a full disk", async () => {
    const store = await IndexedDbLocalStore.open();
    await store.putJob(job("j-1"));

    const db = (store as unknown as { db: { put: (store: string, value: unknown) => Promise<unknown> } })
      .db;
    const put = vi.spyOn(db, "put").mockRejectedValue(quotaError("QuotaExceededError", 22));

    await expect(store.putJob(job("j-2"))).rejects.toBeInstanceOf(StorageFullError);

    // Every later write path — including the outbox — fails fast untouched.
    await expect(
      store.enqueueOutbox({
        id: "rec-1",
        kind: "create",
        entity: "job",
        local_id: null,
        server_id: null,
        payload: {},
        depends_on: [],
        state: "pending",
        attempts: 0,
        last_error: null,
        created_at: "2026-01-01T00:00:00Z",
        acknowledged_at: null,
      }),
    ).rejects.toBeInstanceOf(StorageFullError);
    expect(put).toHaveBeenCalledTimes(1);

    put.mockRestore();
    store.close();
  });
});

describe("MemoryLocalStore", () => {
  it("exposes the same storageFull contract for the fallback store", () => {
    const store = new MemoryLocalStore();
    expect(store.storageFull).toBe(false);
    const listener = vi.fn();
    const unsubscribe = store.subscribeStorageFull(listener);
    unsubscribe();
    expect(listener).not.toHaveBeenCalled();
  });
});
