import { afterEach, describe, expect, it } from "vitest";

import "fake-indexeddb/auto";
import { openDB } from "idb";

import { IndexedDbLocalStore } from "./indexedDbStore";
import { DB_NAME, DB_VERSION } from "./migrations";
import { MemoryLocalStore } from "./memoryStore";
import type { LocalStore, StoredJob, StoredOutcome, StoredStep, StoredTurn } from "./types";

async function makeStore() {
  const store = await IndexedDbLocalStore.open();
  return store;
}

async function clearDb() {
  if (typeof indexedDB !== "undefined") {
    await indexedDB.deleteDatabase(DB_NAME);
  }
}

/** Every store and index the v2 schema declares, read from a live connection. */
async function schemaOf(name: string, version: number) {
  const db = await openDB(name, version);
  const stores = Array.from(db.objectStoreNames).sort();
  const shape = await Promise.all(
    stores.map(async (store) => {
      const tx = db.transaction(store, "readonly");
      const objectStore = tx.objectStore(store);
      return {
        store,
        keyPath: objectStore.keyPath,
        autoIncrement: objectStore.autoIncrement,
        indexes: Array.from(objectStore.indexNames).sort(),
      };
    }),
  );
  db.close();
  return shape;
}

afterEach(async () => {
  await clearDb();
});

describe("IndexedDbLocalStore", () => {
  it("persists jobs across store instances", async () => {
    const store = await makeStore();
    await store.putJob({
      id: "j-1",
      name: "Job",
      description: "d",
      seq: 1,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    });
    store.close();

    const next = await makeStore();
    const jobs = await next.listJobs();
    expect(jobs).toHaveLength(1);
    expect(jobs[0].name).toBe("Job");
    next.close();
  });

  it("orders jobs by seq", async () => {
    const store = await makeStore();
    await store.putJob({
      id: "j-2",
      name: "B",
      description: "",
      seq: 2,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    });
    await store.putJob({
      id: "j-1",
      name: "A",
      description: "",
      seq: 1,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    });

    const jobs = await store.listJobs();
    expect(jobs.map((j) => j.name)).toEqual(["A", "B"]);
    store.close();
  });

  it("supports conversations, turns, and head", async () => {
    const store = await makeStore();
    await store.putConversation({
      id: "c-1",
      title: "Chat",
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
      head_id: null,
    });
    await store.appendTurn({
      conversation_id: "c-1",
      role: "user",
      content: "hi",
      created_at: "2026-01-01T00:00:00Z",
      message_id: "m-1",
      parent_id: null,
    });
    await store.appendTurn({
      conversation_id: "c-1",
      role: "assistant",
      content: "hello",
      created_at: "2026-01-01T00:00:00Z",
      message_id: "m-2",
      parent_id: "m-1",
    });

    const tree = await store.conversationTree("c-1");
    expect(tree.messages.map((m) => m.message_id)).toEqual(["m-1", "m-2"]);
    expect(tree.head_id).toBe("m-2");

    await store.setConversationHead("c-1", "m-1");
    const again = await store.conversationTree("c-1");
    expect(again.head_id).toBe("m-1");
    store.close();
  });

  it("round-trips outbox records and reclaims a stale drain lease", async () => {
    const store = await makeStore();
    await store.enqueueOutbox({
      id: "rec-1",
      kind: "create",
      entity: "job",
      local_id: "local-1",
      server_id: null,
      payload: { name: "Job" },
      depends_on: [],
      state: "pending",
      attempts: 0,
      last_error: null,
      created_at: "2026-01-01T00:00:00Z",
      acknowledged_at: null,
    });
    const queued = await store.listOutbox();
    expect(queued).toHaveLength(1);
    expect(queued[0].payload).toEqual({ name: "Job" });

    // First holder claims the lease; a second tab is turned away.
    expect(await store.claimDrainLease("a", 1_000, 500)).toBeNull();
    expect(await store.claimDrainLease("b", 1_100, 500)).toEqual({
      holder: "a",
      expires_at: 1_500,
    });
    // Past expiry the lease is stale and reclaimable.
    expect(await store.claimDrainLease("b", 1_600, 500)).toBeNull();
    expect(await store.getDrainLease()).toEqual({ holder: "b", expires_at: 2_100 });
    store.close();
  });

  it("snapshots and restores the whole workspace across store instances", async () => {
    const first = await makeStore();
    await first.putJob({
      id: "j-1",
      name: "Job A",
      description: "",
      seq: 1,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    });
    await first.putOutcome({
      id: "o-1",
      job_id: "j-1",
      statement: "Outcome",
      importance: 8,
      satisfaction: 3,
      opportunity_score: 13,
      step_id: null,
      seq: 2,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    });
    await first.putConversation({
      id: "c-1",
      title: "Chat",
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
      head_id: null,
    });
    await first.appendTurn({
      conversation_id: "c-1",
      role: "user",
      content: "hi",
      created_at: "2026-01-01T00:00:00Z",
      message_id: "m-1",
      parent_id: null,
    });
    const snapshot = await first.snapshot();
    first.close();

    const second = await makeStore();
    await second.restore(snapshot);
    const jobs = await second.listJobs();
    expect(jobs.map((j) => j.name)).toEqual(["Job A"]);
    const outcomes = await second.listOutcomes();
    expect(outcomes).toHaveLength(1);
    expect(outcomes[0].opportunity_score).toBe(13);
    const conversations = await second.listConversations();
    expect(conversations).toHaveLength(1);
    const tree = await second.conversationTree("c-1");
    expect(tree.messages.map((m) => m.message_id)).toEqual(["m-1"]);
    second.close();
  });

  it("migrates a seeded v1 database to the current version with every row and the schema intact", async () => {
    await seedV1();

    const before = await rowsOf(DB_NAME, 1);
    expect(Object.keys(before)).toHaveLength(7);
    const store = await makeStore();
    const after = await rowsOf(DB_NAME, DB_VERSION);

    // Every row in all seven v1 stores survives the upgrade, byte for byte.
    for (const name of Object.keys(before)) {
      expect(after[name], `rows in ${name}`).toEqual(before[name]);
    }
    // The later stores are added, and they start empty.
    expect(after.outbox).toEqual([]);
    expect(after.evidence).toEqual([]);
    store.close();

    // The migrated schema equals a fresh database: same stores, key paths,
    // auto-increment flags, and index names.
    const migrated = await schemaOf(DB_NAME, DB_VERSION);
    await clearDb();
    const fresh = await makeStore();
    fresh.close();
    expect(migrated).toEqual(await schemaOf(DB_NAME, DB_VERSION));
    expect(migrated).toEqual(expectedSchema());
  });

  it("closes the old connection and flags a reload when another tab upgrades", async () => {
    const first = await makeStore();
    await first.putJob(job("j-1", "Kept"));

    let reloaded = false;
    first.onVersionChange(() => {
      reloaded = true;
    });

    // A second connection upgrades past this one. Without a versionchange
    // handler the first connection blocks the upgrade and this promise hangs.
    const upgraded = await openDB(DB_NAME, DB_VERSION + 1);
    expect(reloaded).toBe(true);
    expect(first.needsReload).toBe(true);
    // The old connection closed, so the upgrade finished rather than blocking.
    expect(upgraded.version).toBe(DB_VERSION + 1);

    // The rows are still there for the reloaded page to read.
    const jobs = await upgraded.getAll("jobs");
    expect(jobs.map((row) => row.name)).toEqual(["Kept"]);
    upgraded.close();
  });

  it("never needs a reload in the memory-only fallback", () => {
    const store: LocalStore = new MemoryLocalStore();
    expect(store.needsReload).toBe(false);
    expect(store.onVersionChange(() => undefined)).toBeTypeOf("function");
  });
  it("counts the turns a conversation holds", async () => {
    const store = await makeStore();
    await store.putConversation(conversation("c-1", "2026-01-01T00:00:00Z"));
    await store.appendTurn(turn("c-1", "m-1"));
    await store.appendTurn(turn("c-1", "m-2"));

    expect(await store.countTurns("c-1")).toBe(2);
    expect(await store.countTurns("c-none")).toBe(0);
    store.close();
  });

  it("orders conversations the same way the in-memory store does", async () => {
    const rows = [
      conversation("c-middle", "2026-02-05T00:00:00Z"),
      conversation("c-last", "2026-02-09T00:00:00Z"),
      conversation("c-first", "2026-01-01T00:00:00Z"),
    ];
    const indexed = await makeStore();
    const inMemory = new MemoryLocalStore();
    for (const row of rows) {
      await indexed.putConversation(row);
      await inMemory.putConversation(row);
    }

    expect(await indexed.listConversations()).toEqual(await inMemory.listConversations());
    expect((await indexed.listConversations()).map((row) => row.id)).toEqual([
      "c-last",
      "c-middle",
      "c-first",
    ]);
    indexed.close();
  });
});

function conversation(id: string, updatedAt: string) {
  return {
    id,
    title: id,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: updatedAt,
    head_id: null,
  };
}

function turn(conversationId: string, messageId: string) {
  return {
    conversation_id: conversationId,
    role: "user" as const,
    content: "hi",
    created_at: "2026-01-01T00:00:00Z",
    message_id: messageId,
    parent_id: null,
  };
}

function job(id: string, name: string): StoredJob {
  return {
    id,
    name,
    description: "",
    seq: 1,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  };
}

function step(id: string): StoredStep {
  return {
    id,
    job_id: "j-1",
    name: "Step",
    order: 1,
    seq: 2,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  };
}

function outcome(id: string): StoredOutcome {
  return {
    id,
    job_id: "j-1",
    statement: "Minimize the time it takes to decide.",
    importance: 8,
    satisfaction: 3,
    opportunity_score: 13,
    step_id: "s-1",
    seq: 3,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  };
}

/**
 * Seed a v1 database with a row in all seven stores, using the schema the
 * previous release created. This is the fixture the migration must carry
 * forward; the v2 migration is not involved in writing it.
 */
async function seedV1(): Promise<void> {
  const legacy = await openDB(DB_NAME, 1, {
    upgrade(database) {
      database.createObjectStore("meta", { keyPath: "key" });
      const jobs = database.createObjectStore("jobs", { keyPath: "id" });
      jobs.createIndex("by-seq", "seq");
      const steps = database.createObjectStore("steps", { keyPath: "id" });
      steps.createIndex("by-job", "job_id");
      steps.createIndex("by-seq", "seq");
      const outcomes = database.createObjectStore("outcomes", { keyPath: "id" });
      outcomes.createIndex("by-job", "job_id");
      outcomes.createIndex("by-seq", "seq");
      const observations = database.createObjectStore("observations", {
        keyPath: "id",
      });
      observations.createIndex("by-created", "created_at");
      const conversations = database.createObjectStore("conversations", {
        keyPath: "id",
      });
      conversations.createIndex("by-updated", "updated_at");
      const turns = database.createObjectStore("turns", {
        keyPath: "id",
        autoIncrement: true,
      });
      turns.createIndex("by-conversation", "conversation_id");
    },
  });
  await legacy.put("meta", { key: "seq", value: 3 });
  await legacy.put("jobs", job("j-1", "Legacy Job"));
  await legacy.put("steps", step("s-1"));
  await legacy.put("outcomes", outcome("o-1"));
  await legacy.put("observations", {
    id: "ob-1",
    kind: "business",
    text: "Legacy observation",
    data: {},
    status: "confirmed",
    confidence: 0.5,
    source_turn: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  });
  await legacy.put("conversations", conversation("c-1", "2026-01-01T00:00:00Z"));
  await legacy.put("turns", turn("c-1", "m-1") as StoredTurn);
  legacy.close();
}

/** Every row in every store, keyed by store name, read from a live database. */
async function rowsOf(name: string, version: number) {
  const db = await openDB(name, version);
  const stores = Array.from(db.objectStoreNames).sort();
  const rows: Record<string, unknown[]> = {};
  for (const store of stores) {
    rows[store] = await db.getAll(store);
  }
  db.close();
  return rows;
}

/** The current schema written out, so the migrated shape is asserted, not assumed. */
function expectedSchema() {
  return [
    {
      store: "conversations",
      keyPath: "id",
      autoIncrement: false,
      indexes: ["by-updated"],
    },
    {
      store: "evidence",
      keyPath: "id",
      autoIncrement: false,
      indexes: ["by-job", "by-seq"],
    },
    {
      store: "jobs",
      keyPath: "id",
      autoIncrement: false,
      indexes: ["by-seq"],
    },
    {
      store: "meta",
      keyPath: "key",
      autoIncrement: false,
      indexes: [],
    },
    {
      store: "notices",
      keyPath: "id",
      autoIncrement: false,
      indexes: ["by-at"],
    },
    {
      store: "observations",
      keyPath: "id",
      autoIncrement: false,
      indexes: ["by-created"],
    },
    {
      store: "outbox",
      keyPath: "id",
      autoIncrement: false,
      indexes: ["by-created", "by-state"],
    },
    {
      store: "outcomes",
      keyPath: "id",
      autoIncrement: false,
      indexes: ["by-job", "by-seq"],
    },
    {
      store: "steps",
      keyPath: "id",
      autoIncrement: false,
      indexes: ["by-job", "by-seq"],
    },
    {
      store: "turns",
      keyPath: "id",
      autoIncrement: true,
      indexes: ["by-conversation"],
    },
  ];
}
