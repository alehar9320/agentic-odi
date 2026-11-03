import { describe, expect, it } from "vitest";

import { LocalMemoryService } from "../bff/memory/localMemoryService";
import { MemoryLocalStore } from "../bff/store/memoryStore";
import { readEdgeTurns, recordEdgeTurn } from "./transcript";

function makeMemory(): LocalMemoryService {
  return new LocalMemoryService(new MemoryLocalStore());
}

async function recordOneTurn(memory: LocalMemoryService): Promise<void> {
  await recordEdgeTurn(memory, {
    conversationId: "conv-1",
    question: { id: "q-1", text: "Where do I start?", parentId: null },
    answer: { id: "a-1", text: "Start with the job, then the outcome." },
  });
}

describe("recordEdgeTurn", () => {
  it("holds a turn for a conversation id the server minted", async () => {
    const memory = makeMemory();
    await recordOneTurn(memory);

    const turns = await readEdgeTurns(memory, "conv-1");
    expect(turns.map((turn) => turn.id)).toEqual(["q-1", "a-1"]);
    expect(turns.map((turn) => turn.role)).toEqual(["user", "assistant"]);
  });

  it("hangs the browser's answer off the question it answers", async () => {
    const memory = makeMemory();
    await recordOneTurn(memory);

    const turns = await readEdgeTurns(memory, "conv-1");
    expect(turns[0]?.parent_id).toBeNull();
    expect(turns[1]?.parent_id).toBe("q-1");
  });

  it("keeps the words the browser produced", async () => {
    const memory = makeMemory();
    await recordOneTurn(memory);

    const turns = await readEdgeTurns(memory, "conv-1");
    expect(turns.map((turn) => turn.content)).toEqual([
      "Where do I start?",
      "Start with the job, then the outcome.",
    ]);
  });

  it("records the reply, and only the reply, as this browser's", async () => {
    const memory = makeMemory();
    await recordOneTurn(memory);

    const turns = await readEdgeTurns(memory, "conv-1");
    expect(turns[1]?.provenance).toBe("edge");
    expect(turns[0]?.provenance).toBeUndefined();
  });

  it("attaches a turn to the thread the person was already looking at", async () => {
    const memory = makeMemory();
    await memory.ensureConversation("conv-0");
    await memory.appendTurn("conv-0", "user", "asked while the server was up", "q-0", null);
    await recordEdgeTurn(memory, {
      conversationId: "conv-0",
      question: { id: "q-1", text: "And now?", parentId: "q-0" },
      answer: { id: "a-1", text: "Now in this browser." },
    });

    const turns = await readEdgeTurns(memory, "conv-0");
    expect(turns.map((turn) => turn.id)).toEqual(["q-0", "q-1", "a-1"]);
    expect(turns[1]?.parent_id).toBe("q-0");
  });

  it("reads nothing for a conversation this browser never answered", async () => {
    const memory = makeMemory();
    expect(await readEdgeTurns(memory, "conv-none")).toEqual([]);
  });
});
