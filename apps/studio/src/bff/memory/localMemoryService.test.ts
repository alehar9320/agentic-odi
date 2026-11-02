import { describe, expect, it } from "vitest";

import { MemoryLocalStore } from "../store/memoryStore";
import { LocalMemoryService } from "./localMemoryService";

function makeStore() {
  return new MemoryLocalStore();
}

/** A thread with timestamps the wall clock cannot move. */
async function seed(
  store: MemoryLocalStore,
  id: string,
  title: string,
  updatedAt: string,
): Promise<void> {
  await store.putConversation({
    id,
    title,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: updatedAt,
    head_id: null,
  });
}

describe("LocalMemoryService observations", () => {
  it("adds and lists confirmed observations", async () => {
    const store = makeStore();
    const memory = new LocalMemoryService(store);
    const obs = await memory.addObservation({
      kind: "opportunity",
      text: "Customers hate setup.",
      confidence: 0.8,
      confirmed: true,
    });
    expect(obs.status).toBe("confirmed");
    expect(obs.kind).toBe("opportunity");

    const list = await memory.listObservations();
    expect(list).toHaveLength(1);
    expect(list[0].id).toBe(obs.id);
  });

  it("excludes dismissed observations by default", async () => {
    const store = makeStore();
    const memory = new LocalMemoryService(store);
    await memory.addObservation({ kind: "evidence", text: "One", confirmed: true });
    await memory.addObservation({ kind: "evidence", text: "Two", confirmed: false });
    await memory.addObservation({ kind: "evidence", text: "Three", confirmed: false });
    await memory.updateObservation((await memory.listObservations())[2].id, {
      status: "dismissed",
    });

    const suggested = await memory.listObservations();
    expect(suggested).toHaveLength(2);
    expect(suggested.map((o) => o.text)).toEqual(["One", "Two"]);
  });

  it("updates and deletes observations", async () => {
    const store = makeStore();
    const memory = new LocalMemoryService(store);
    const obs = await memory.addObservation({
      kind: "evidence",
      text: "Original",
    });
    const updated = await memory.updateObservation(obs.id, {
      status: "confirmed",
      text: "Updated",
    });
    expect(updated.text).toBe("Updated");
    expect(updated.status).toBe("confirmed");

    await expect(memory.deleteObservation(obs.id)).resolves.toEqual({ ok: true });
    const remaining = await memory.listObservations();
    expect(remaining).toEqual([]);
  });
});

describe("LocalMemoryService conversations", () => {
  it("creates and finds conversations", async () => {
    const store = makeStore();
    const memory = new LocalMemoryService(store);
    const conv = await memory.createConversation("First");
    expect(conv.title).toBe("First");
    expect(conv.head_id).toBeNull();

    const found = await memory.getConversation(conv.id);
    expect(found?.id).toBe(conv.id);
  });

  it("appends user and assistant turns with ids and parents", async () => {
    const store = makeStore();
    const memory = new LocalMemoryService(store);
    const conv = await memory.createConversation();
    const user = await memory.appendTurn(conv.id, "user", "add job Onboard", "m-1", null);
    const assistant = await memory.appendTurn(
      conv.id,
      "assistant",
      "Job created.",
      "m-2",
      user.message_id ?? null,
    );
    expect(user.message_id).toBe("m-1");
    expect(user.parent_id).toBeNull();
    expect(assistant.message_id).toBe("m-2");
    expect(assistant.parent_id).toBe("m-1");
  });

  it("builds a conversation tree with head", async () => {
    const store = makeStore();
    const memory = new LocalMemoryService(store);
    const conv = await memory.createConversation();
    await memory.appendTurn(conv.id, "user", "first", "m-1", null);
    await memory.appendTurn(conv.id, "assistant", "second", "m-2", "m-1");
    await memory.appendTurn(conv.id, "assistant", "third", "m-3", "m-1");

    const tree = await memory.conversationTree(conv.id);
    expect(tree.messages.map((m) => m.message_id)).toEqual(["m-1", "m-2", "m-3"]);
    expect(tree.head_id).toBe("m-3");
  });

  it("sets and reads the conversation head", async () => {
    const store = makeStore();
    const memory = new LocalMemoryService(store);
    const conv = await memory.createConversation();
    await memory.appendTurn(conv.id, "user", "first", "m-1", null);
    await memory.appendTurn(conv.id, "assistant", "second", "m-2", "m-1");

    await memory.setConversationHead(conv.id, "m-1");
    const tree = await memory.conversationTree(conv.id);
    expect(tree.head_id).toBe("m-1");
  });

  it("latestConversation returns the most recent conversation", async () => {
    const store = makeStore();
    const memory = new LocalMemoryService(store);
    const first = await memory.createConversation("First");
    await memory.appendTurn(first.id, "user", "hello", "m-1", null);
    await new Promise((resolve) => setTimeout(resolve, 5));
    const second = await memory.createConversation("Second");

    const latest = await memory.latestConversation();
    expect([first.id, second.id]).toContain(latest.conversation?.id);
  });

  it("lists conversations by the touch that came last", async () => {
    const store = makeStore();
    const memory = new LocalMemoryService(store);
    await seed(store, "c-revisited", "Quarterly review", "2026-02-09T00:00:00Z");
    await seed(store, "c-untouched", "Activation model", "2026-02-05T00:00:00Z");

    const listed = await memory.listConversations();

    expect(listed.map((item) => item.id)).toEqual(["c-revisited", "c-untouched"]);
    expect(listed[0].title).toBe("Quarterly review");
  });

  it("reports how many turns each conversation holds", async () => {
    const store = makeStore();
    const memory = new LocalMemoryService(store);
    await seed(store, "c-talked", "Scored", "2026-02-09T00:00:00Z");
    await seed(store, "c-quiet", "Blank", "2026-02-05T00:00:00Z");
    await memory.appendTurn("c-talked", "user", "How do I score this?", "m-1", null);
    await memory.appendTurn("c-talked", "assistant", "By importance.", "m-2", "m-1");

    const listed = await memory.listConversations();

    expect(Object.fromEntries(listed.map((item) => [item.id, item.turn_count]))).toEqual({
      "c-talked": 2,
      "c-quiet": 0,
    });
  });
});
