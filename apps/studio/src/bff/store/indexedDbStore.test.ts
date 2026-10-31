import { afterEach, describe, expect, it } from "vitest";

import "fake-indexeddb/auto";

import { IndexedDbLocalStore } from "./indexedDbStore";

async function makeStore() {
  const store = await IndexedDbLocalStore.open();
  return store;
}

async function clearDb() {
  if (typeof indexedDB !== "undefined") {
    await indexedDB.deleteDatabase("agentic-odi-studio");
  }
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
      id: "m-1",
      parent_id: null,
    });
    await store.appendTurn({
      conversation_id: "c-1",
      role: "assistant",
      content: "hello",
      created_at: "2026-01-01T00:00:00Z",
      id: "m-2",
      parent_id: "m-1",
    });

    const tree = await store.conversationTree("c-1");
    expect(tree.messages.map((m) => m.id)).toEqual(["m-1", "m-2"]);
    expect(tree.head_id).toBe("m-2");

    await store.setConversationHead("c-1", "m-1");
    const again = await store.conversationTree("c-1");
    expect(again.head_id).toBe("m-1");
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
      id: "m-1",
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
    expect(tree.messages.map((m) => m.id)).toEqual(["m-1"]);
    second.close();
  });
});
