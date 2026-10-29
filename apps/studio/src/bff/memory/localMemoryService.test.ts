import { describe, expect, it } from "vitest";

import { MemoryLocalStore } from "../store/memoryStore";
import { LocalMemoryService } from "./localMemoryService";

function makeStore() {
  return new MemoryLocalStore();
}

describe("LocalMemoryService observations", () => {
  it("proposes a note the agent wrote, and confirms only what the person confirmed", async () => {
    const memory = new LocalMemoryService(makeStore());
    const agent = await memory.addObservation({
      category: "opportunity",
      text: "Customers hate setup.",
      confidence: 0.8,
    });
    expect(agent.status).toBe("proposed");
    expect(agent.category).toBe("opportunity");

    const human = await memory.addObservation({
      category: "constraint",
      text: "Pricing is frozen this quarter.",
      confirmed: true,
    });
    expect(human.status).toBe("confirmed");
  });

  it("excludes dismissed observations, from the list and from the prompt context", async () => {
    const memory = new LocalMemoryService(makeStore());
    const kept = await memory.addObservation({ category: "evidence", text: "One", confirmed: true });
    const dismissed = await memory.addObservation({ category: "evidence", text: "Two" });
    await memory.updateObservation(dismissed.id, { status: "dismissed" });

    const list = await memory.listObservations();
    expect(list.map((observation) => observation.id)).toEqual([kept.id]);
    expect((await memory.listObservations(true)).map((observation) => observation.text).sort()).toEqual([
      "One",
      "Two",
    ]);

    const context = await memory.memoryContext();
    expect(context).toContain("One");
    expect(context).not.toContain("Two");
  });

  it("updates and deletes observations", async () => {
    const memory = new LocalMemoryService(makeStore());
    const obs = await memory.addObservation({ category: "evidence", text: "Original" });
    const updated = await memory.updateObservation(obs.id, {
      status: "confirmed",
      text: "Updated",
      category: "decision",
    });
    expect(updated.text).toBe("Updated");
    expect(updated.status).toBe("confirmed");
    expect(updated.category).toBe("decision");

    await expect(memory.deleteObservation(obs.id)).resolves.toEqual({ ok: true });
    expect(await memory.listObservations()).toEqual([]);
  });

  it("refuses a category the store does not know", async () => {
    const memory = new LocalMemoryService(makeStore());
    await expect(
      memory.addObservation({ category: "mood", text: "Feeling optimistic." }),
    ).rejects.toThrow(/Unknown observation category/);
  });

  it("records where a note came from", async () => {
    const memory = new LocalMemoryService(makeStore());
    const conversation = await memory.createConversation();
    const turn = await memory.appendTurn(conversation.id, "user", "we always plan on Mondays");
    const observation = await memory.addObservation({
      category: "preference",
      text: "Plans on Mondays.",
      conversationId: conversation.id,
      sourceMessageId: turn.id,
    });
    expect(observation.conversation_id).toBe(conversation.id);
    expect(observation.source_message_id).toBe(turn.id);
  });
});

describe("LocalMemoryService conversations", () => {
  it("starts a conversation unnamed, and names it from the first thing said", async () => {
    const memory = new LocalMemoryService(makeStore());
    const conversation = await memory.createConversation();
    expect(conversation.title).toBeNull();
    expect(conversation.head_id).toBeNull();
    expect(conversation.archived).toBe(false);

    await memory.appendTurn(conversation.id, "user", "add job Onboard customers");
    const found = await memory.getConversation(conversation.id);
    expect(found?.title).toBe("add job Onboard customers");
  });

  it("keeps the ids and parents it is given, so a reload is the same tree", async () => {
    const memory = new LocalMemoryService(makeStore());
    const conversation = await memory.createConversation();
    const user = await memory.appendTurn(conversation.id, "user", "first", "m-1");
    const assistant = await memory.appendTurn(conversation.id, "assistant", "second", "m-2", "m-1");

    expect(user.id).toBe("m-1");
    expect(user.parent_id).toBeNull();
    expect(assistant.id).toBe("m-2");
    expect(assistant.parent_id).toBe("m-1");
  });

  it("heads the conversation at the newest turn and can reopen an older branch", async () => {
    const memory = new LocalMemoryService(makeStore());
    const conversation = await memory.createConversation();
    await memory.appendTurn(conversation.id, "user", "first", "m-1");
    await memory.appendTurn(conversation.id, "assistant", "second", "m-2", "m-1");
    await memory.appendTurn(conversation.id, "assistant", "third", "m-3", "m-1");

    const tree = await memory.conversationTree(conversation.id);
    expect(tree.messages.map((turn) => turn.id)).toEqual(["m-1", "m-2", "m-3"]);
    expect(tree.head_id).toBe("m-3");

    await memory.setConversationHead(conversation.id, "m-1");
    expect((await memory.conversationTree(conversation.id)).head_id).toBe("m-1");
  });

  it("stores the parts alongside the prose", async () => {
    const memory = new LocalMemoryService(makeStore());
    const conversation = await memory.createConversation();
    const turn = await memory.appendTurn(conversation.id, "assistant", "Look at this", "m-1", null, [
      { kind: "text", text: "Look at this" },
      { kind: "reasoning", text: "choosing a surface" },
    ]);
    expect(turn.parts).toHaveLength(2);
    const tree = await memory.conversationTree(conversation.id);
    expect(tree.messages[0].parts?.[1]).toEqual({ kind: "reasoning", text: "choosing a surface" });
  });

  it("archives and restores without losing a word", async () => {
    const memory = new LocalMemoryService(makeStore());
    const conversation = await memory.createConversation();
    await memory.appendTurn(conversation.id, "user", "keep me");

    await memory.setConversationArchived(conversation.id, true);
    expect((await memory.getConversation(conversation.id))?.archived).toBe(true);
    expect((await memory.listTurns(conversation.id))[0].content).toBe("keep me");

    await memory.setConversationArchived(conversation.id, false);
    expect((await memory.getConversation(conversation.id))?.archived).toBe(false);
  });

  it("deleting a conversation takes its turns with it", async () => {
    const memory = new LocalMemoryService(makeStore());
    const conversation = await memory.createConversation();
    await memory.appendTurn(conversation.id, "user", "gone soon");

    await memory.deleteConversation(conversation.id);
    expect(await memory.getConversation(conversation.id)).toBeUndefined();
    await expect(memory.listTurns(conversation.id)).rejects.toThrow(/not found/i);
  });

  it("lists conversations newest first", async () => {
    const memory = new LocalMemoryService(makeStore());
    const first = await memory.createConversation("First");
    await new Promise((resolve) => setTimeout(resolve, 5));
    const second = await memory.createConversation("Second");

    const list = await memory.listConversations();
    expect(list[0].id).toBe(second.id);
    expect(list.map((conversation) => conversation.id)).toContain(first.id);
  });

  it("injects confirmed context only, and never a dismissed note", async () => {
    const memory = new LocalMemoryService(makeStore());
    await memory.addObservation({ category: "career", text: "Leads a small team.", confirmed: true });
    await memory.addObservation({ category: "business", text: "Maybe an MVP." });

    const context = await memory.memoryContext();
    expect(context).toContain("Leads a small team.");
    expect(context).not.toContain("Maybe an MVP.");
  });
});
