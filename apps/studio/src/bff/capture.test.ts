import { afterEach, describe, expect, it } from "vitest";

import "fake-indexeddb/auto";

import { listQueuedCaptures, replayCaptures } from "./capture";
import { LocalDataService } from "./data/localDataService";
import { IndexedDbLocalStore } from "./store/indexedDbStore";
import { DB_NAME } from "./store/migrations";
import { MemoryLocalStore } from "./store/memoryStore";
import type { OutboxRecord } from "./store/types";

async function clearDb() {
  if (typeof indexedDB !== "undefined") {
    await indexedDB.deleteDatabase(DB_NAME);
  }
}

afterEach(async () => {
  await clearDb();
});

/** A sidecar that stores each capture once, keyed by its idempotency key. */
class FakeSidecar {
  readonly stored = new Map<string, OutboxRecord>();
  sends = 0;
  /** When set, the next send stores the record and then loses the response. */
  loseNextResponse = false;

  send = async (record: OutboxRecord): Promise<void> => {
    this.sends += 1;
    this.stored.set(record.id, record);
    if (this.loseNextResponse) {
      this.loseNextResponse = false;
      throw new TypeError("Failed to fetch");
    }
  };
}

const CAPTURE = {
  statement: "Minimize the time it takes to ship",
  importance: 8,
  satisfaction: 3,
};

describe("queueCapture", () => {
  it("survives a reload: the capture is still queued in a fresh store", async () => {
    const first = await IndexedDbLocalStore.open();
    const service = new LocalDataService(first);
    const job = await service.createJob({ name: "Ship a service" });
    await service.queueCapture({ job_id: job.id, ...CAPTURE });
    expect(await service.countQueuedCaptures()).toBe(1);
    first.close();

    // A reload opens the same database again; nothing was held in memory.
    const reloaded = await IndexedDbLocalStore.open();
    const reloadedService = new LocalDataService(reloaded);
    const queued = await reloadedService.listQueuedCaptures();
    expect(queued).toHaveLength(1);
    expect(queued[0]).toMatchObject({ job_id: job.id, ...CAPTURE, pending: true });
    reloaded.close();
  });

  it("mints the idempotency key at capture time, not at replay", async () => {
    const store = new MemoryLocalStore();
    const service = new LocalDataService(store);
    const job = await service.createJob({ name: "Ship a service" });
    const captured = await service.queueCapture({ job_id: job.id, ...CAPTURE });
    const [queued] = await listQueuedCaptures(store);
    expect(queued.id).toBe(captured.id);
    expect(queued.id).not.toBe("");
  });

  it("rejects a capture for a job the store does not know", async () => {
    const store = new MemoryLocalStore();
    const service = new LocalDataService(store);
    await expect(service.queueCapture({ job_id: "JOB-missing", ...CAPTURE })).rejects.toThrow();
  });
});

describe("replayCaptures", () => {
  it("arrives once when a lost response forces a second replay", async () => {
    const store = new MemoryLocalStore();
    const service = new LocalDataService(store);
    const job = await service.createJob({ name: "Ship a service" });
    const sidecar = new FakeSidecar();
    await service.queueCapture({ job_id: job.id, ...CAPTURE });

    // The first send reaches the sidecar and the response is lost, so the
    // record stays pending and the person's connection retries it.
    sidecar.loseNextResponse = true;
    await expect(replayCaptures({ store, send: sidecar.send })).rejects.toThrow();
    expect(await service.countQueuedCaptures()).toBe(1);

    const sent = await replayCaptures({ store, send: sidecar.send });
    expect(sent).toBe(1);
    expect(await service.countQueuedCaptures()).toBe(0);

    // Two sends, one stored record: the idempotency key made the second a
    // no-op instead of a duplicate.
    expect(sidecar.sends).toBe(2);
    expect(sidecar.stored.size).toBe(1);
  });

  it("leaves other pending records for the path that owns them", async () => {
    const store = new MemoryLocalStore();
    const service = new LocalDataService(store);
    const job = await service.createJob({ name: "Ship a service" });
    await service.queueCapture({ job_id: job.id, ...CAPTURE });
    await store.enqueueOutbox({
      id: "edit-1",
      kind: "update",
      entity: "job",
      local_id: job.id,
      server_id: null,
      payload: {},
      depends_on: [],
      state: "pending",
      attempts: 0,
      last_error: null,
      created_at: "2026-01-01T00:00:00.000Z",
      acknowledged_at: null,
    });

    const sent: string[] = [];
    await replayCaptures({
      store,
      send: (record) => {
        sent.push(record.id);
      },
    });

    expect(sent).toHaveLength(1);
    expect(await store.getOutbox("edit-1")).toMatchObject({ state: "pending" });
  });
});

describe("capture queue count", () => {
  it("counts only the captures still pending", async () => {
    const store = new MemoryLocalStore();
    const service = new LocalDataService(store);
    const job = await service.createJob({ name: "Ship a service" });
    await service.queueCapture({ job_id: job.id, ...CAPTURE });
    await service.queueCapture({
      job_id: job.id,
      statement: "Maximize the number of interviews booked",
      importance: 6,
      satisfaction: 4,
    });
    expect(await service.countQueuedCaptures()).toBe(2);
  });
});
