import { describe, expect, it } from "vitest";

import type { RawSseEvent } from "../api/sse";
import type { ChatMessage, ChatStreamRequest } from "../types";
import { edgeTurn } from "./turn";
import { buildEdgeMessages, edgeSystemPrompt } from "./prompt";
import { FakeEdgeEngine } from "../test/edgeFake";

const baseRequest: ChatStreamRequest = {
  base_url: "",
  api_key: "",
  model: "",
  mcp_url: "",
  messages: [],
  brief: null,
};

function turn(...roles: Array<"user" | "assistant" | "notice">): ChatMessage[] {
  return roles.map((role, index) => ({
    id: `m-${index}`,
    parentId: index ? `m-${index - 1}` : null,
    role,
    content: `${role} ${index}`,
  }));
}

function collect(): { events: RawSseEvent[]; onEvent: (event: RawSseEvent) => void } {
  const events: RawSseEvent[] = [];
  return { events, onEvent: (event) => events.push(event) };
}

describe("edgeTurn frame contract", () => {
  it("streams status → deltas → a single terminal message", async () => {
    const engine = new FakeEdgeEngine({ tokens: ["Free", " local", " models."] });
    const { events, onEvent } = collect();

    await edgeTurn({ ...baseRequest, messages: turn("user") }, { engine, modelId: "m" }, onEvent);

    expect(events.map((event) => event.event)).toEqual([
      "status",
      "delta",
      "delta",
      "delta",
      "message",
    ]);
    expect(events[0].data.phase).toBe("model");
    expect(events.at(-1)?.data.content).toBe("Free local models.");
    expect(events.at(-1)?.data.claims).toBeUndefined();
  });

  it("reports an engine failure as a retryable studio error, once", async () => {
    const engine = new FakeEdgeEngine({ failWith: new Error("device lost") });
    const { events, onEvent } = collect();

    await edgeTurn({ ...baseRequest, messages: turn("user") }, { engine, modelId: "m" }, onEvent);

    const kinds = events.map((event) => event.event);
    expect(kinds).toEqual(["status", "error"]);
    const error = events[1].data.error as Record<string, unknown>;
    expect(error.code).toBe("edge_stream_failed");
    expect(error.retryable).toBe(true);
    expect(error.detail).toBe("device lost");
  });

  it("goes silent when the user aborts: no terminal, no failure", async () => {
    const controller = new AbortController();
    const engine = {
      probe: async () => {
        throw new Error("unused");
      },
      load: async () => {},
      unload: async () => {},
      async *stream() {
        yield "start";
        controller.abort();
        yield "never reaches the transcript";
      },
    };
    const { events, onEvent } = collect();

    await edgeTurn(
      { ...baseRequest, messages: turn("user") },
      { engine, modelId: "m" },
      onEvent,
      controller.signal,
    );

    const kinds = events.map((event) => event.event);
    expect(kinds).toEqual(["status", "delta"]);
    // The abort lands while the generator resumes, so only the pre-abort
    // token is emitted and the turn ends exactly like a user-stop: the
    // partial text stays as streamed, and no `message`/`error` frame follows.
  });
});

describe("edge prompt", () => {
  it("leads with the local-assistant persona and admits what it cannot do", () => {
    const prompt = edgeSystemPrompt(baseRequest);
    expect(prompt).toMatch(/running locally in this person's browser/);
    expect(prompt).toMatch(/Never invent numbers/);
    expect(prompt).toMatch(/cannot add, change, or fetch stored data/);
    expect(prompt).not.toMatch(/briefDigest|product_name/);
  });

  it("grounds the model in the brief when there is one", () => {
    const prompt = edgeSystemPrompt({
      ...baseRequest,
      brief: {
        product_name: "Fieldnotes",
        target_user: "night-shift nurses",
        job_statement: "hand over a ward safely in five minutes",
        core_problem: "important details get lost between shifts",
        evidence_at_hand: ["unit call logs"],
      },
    });
    expect(prompt).toContain("hand over a ward safely in five minutes");
    expect(prompt).toContain("night-shift nurses");
    expect(prompt).toContain("unit call logs");
  });

  it("keeps only conversational roles, inside a twelve-message window", () => {
    const mixed = turn(
      ...Array.from({ length: 14 }, (_, i) => (i % 5 === 4 ? ("notice" as const) : ("user" as const))),
    );
    const messages = buildEdgeMessages({ ...baseRequest, messages: mixed });
    expect(messages[0].role).toBe("system");
    expect(messages.slice(1).every((message) => !message.content.startsWith("notice"))).toBe(true);
    expect(messages).toHaveLength(13);
  });

  it("folds the canvas digest in when supplied", () => {
    const prompt = edgeSystemPrompt(baseRequest, "3 jobs, 12 outcomes");
    expect(prompt).toContain("3 jobs, 12 outcomes");
  });
});
