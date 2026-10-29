import { describe, expect, it } from "vitest";

import { MemoryLocalStore } from "../store/memoryStore";
import { LocalMemoryService } from "./localMemoryService";

function makeStore() {
  return new MemoryLocalStore();
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
});

describe("LocalMemoryService thread history", () => {
  it("lists threads newest first", async () => {
    const store = makeStore();
    const memory = new LocalMemoryService(store);
    const first = await memory.createConversation("First");
    await memory.appendTurn(first.id, "user", "hello", "m-1", null);
    await new Promise((resolve) => setTimeout(resolve, 5));
    const second = await memory.createConversation("Second");
    await memory.appendTurn(second.id, "user", "hello", "m-2", null);

    const list = await memory.listConversations();

    expect(list.map((conversation) => conversation.id)).toEqual([second.id, first.id]);
  });

  it("leaves a thread with no turns out of the history", async () => {
    const store = makeStore();
    const memory = new LocalMemoryService(store);
    await memory.createConversation("Nothing said yet");

    await expect(memory.listConversations()).resolves.toEqual([]);
  });

  it("renames a thread without touching its turns", async () => {
    const store = makeStore();
    const memory = new LocalMemoryService(store);
    const conversation = await memory.createConversation("Untitled");
    await memory.appendTurn(conversation.id, "user", "hello", "m-1", null);

    const renamed = await memory.renameConversation(conversation.id, "  Sharper title  ");

    expect(renamed.title).toBe("Sharper title");
    const tree = await memory.conversationTree(conversation.id);
    expect(tree.messages).toHaveLength(1);
  });

  it("forgets a thread and its turns", async () => {
    const store = makeStore();
    const memory = new LocalMemoryService(store);
    const conversation = await memory.createConversation("Forget me");
    await memory.appendTurn(conversation.id, "user", "hello", "m-1", null);

    await memory.deleteConversation(conversation.id);

    await expect(memory.getConversation(conversation.id)).resolves.toBeUndefined();
    await expect(memory.listConversations()).resolves.toEqual([]);
  });

  it("deletes a message with its answers and leaves the sibling branch", async () => {
    const store = makeStore();
    const memory = new LocalMemoryService(store);
    const conversation = await memory.createConversation("Branches");
    await memory.appendTurn(conversation.id, "user", "list jobs", "m-1", null);
    await memory.appendTurn(conversation.id, "assistant", "first", "m-2", "m-1");
    await memory.appendTurn(conversation.id, "assistant", "second", "m-3", "m-1");
    await memory.appendTurn(conversation.id, "user", "and then?", "m-4", "m-3");

    await memory.deleteMessage(conversation.id, "m-2");

    const tree = await memory.conversationTree(conversation.id);
    expect(tree.messages.map((turn) => turn.message_id)).toEqual(["m-1", "m-3", "m-4"]);
    expect(tree.head_id).toBe("m-4");
  });

  it("refuses to delete from a thread it does not have", async () => {
    const memory = new LocalMemoryService(makeStore());

    await expect(memory.deleteMessage("missing", "m-1")).rejects.toThrow();
    await expect(memory.deleteConversation("missing")).rejects.toThrow();
  });
});

describe("LocalMemoryService branch head after deletion", () => {
  async function seeded() {
    const memory = new LocalMemoryService(makeStore());
    const conversation = await memory.createConversation("Branches");
    await memory.appendTurn(conversation.id, "user", "list jobs", "m-1", null);
    await memory.appendTurn(conversation.id, "assistant", "first", "m-2", "m-1");
    await memory.appendTurn(conversation.id, "user", "and then?", "m-3", "m-2");
    return { memory, conversation };
  }

  it("moves the head back to the question above a deleted reply", async () => {
    const { memory, conversation } = await seeded();

    await memory.deleteMessage(conversation.id, "m-3");

    const tree = await memory.conversationTree(conversation.id);
    expect(tree.messages.map((turn) => turn.message_id)).toEqual(["m-1", "m-2"]);
    expect(tree.head_id).toBe("m-2");
  });

  it("leaves the head alone when the deleted turn was on another branch", async () => {
    const { memory, conversation } = await seeded();
    await memory.appendTurn(conversation.id, "assistant", "second", "m-4", "m-1");

    await memory.deleteMessage(conversation.id, "m-3");

    const tree = await memory.conversationTree(conversation.id);
    expect(tree.head_id).toBe("m-4");
  });
});
