import { describe, expect, it } from "vitest";

import type { ChatMessage } from "../types";
import { catalogManifest } from "../ui/catalog";
import { parseUiSpec, type UiNode } from "../ui/protocol";
import { SURFACE_PART, textOf, toThreadMessageLike } from "./convert";

function nodeOf(spec: unknown): UiNode {
  const parsed = parseUiSpec(spec, catalogManifest());
  if (!parsed.ok) {
    throw new Error(parsed.reason);
  }
  return parsed.node;
}

const card = nodeOf({
  type: "outcome-card",
  props: {
    id: "O-1",
    statement: "Minimize the time it takes to propagate secrets",
    importance: 9,
    satisfaction: 3,
  },
});

function assistant(overrides: Partial<ChatMessage> = {}): ChatMessage {
  return {
    id: "m-1",
    parentId: null,
    role: "assistant",
    content: "",
    ...overrides,
  };
}

describe("toThreadMessageLike", () => {
  it("maps prose to a text part", () => {
    const message = toThreadMessageLike(assistant({ content: "Hello." }));

    expect(message.role).toBe("assistant");
    expect(message.content).toEqual([{ type: "text", text: "Hello." }]);
  });

  it("keeps the agent's part order", () => {
    const message = toThreadMessageLike(
      assistant({
        content: "beforeafter",
        parts: [
          { kind: "text", text: "before" },
          { kind: "ui", id: "ui-1", node: card },
          { kind: "text", text: "after" },
        ],
      }),
    );

    expect((message.content as unknown as { type: string }[]).map((part) => part.type)).toEqual([
      "text",
      "data",
      "text",
    ]);
  });

  it("carries a generated surface as a named data part", () => {
    const message = toThreadMessageLike(
      assistant({
        parts: [{ kind: "ui", id: "ui-1", node: card }],
      }),
    );

    const part = (message.content as { type: string; name?: string; id?: string; data?: UiNode }[])[0];
    expect(part.type).toBe("data");
    expect(part.name).toBe(SURFACE_PART);
    expect(part.id).toBe("ui-1");
    expect(part.data).toEqual(card);
  });

  it("maps reasoning to a reasoning part", () => {
    const message = toThreadMessageLike(
      assistant({ parts: [{ kind: "reasoning", text: "weighing options" }] }),
    );

    expect(message.content).toEqual([
      { type: "reasoning", text: "weighing options", status: { type: "complete" } },
    ]);
  });

  it("marks the live turn's parts as running until it settles", () => {
    const message = toThreadMessageLike(
      assistant({
        parts: [
          { kind: "text", text: "Looking" },
          { kind: "reasoning", text: "weighing options" },
        ],
      }),
      { live: true },
    );

    expect(message.status).toEqual({ type: "running" });
    expect(message.content).toEqual([
      { type: "text", text: "Looking", status: { type: "running" } },
      { type: "reasoning", text: "weighing options", status: { type: "running" } },
    ]);
  });

  it("maps a finished tool call to a result, not a question", () => {
    const message = toThreadMessageLike(
      assistant({
        parts: [
          { kind: "tool", id: "call-1", name: "get_jobs", status: "ok", preview: "3 jobs" },
        ],
      }),
    );

    const part = (
      message.content as {
        type: string;
        toolCallId?: string;
        toolName?: string;
        result?: { status?: string; preview?: string };
        isError?: boolean;
      }[]
    )[0];
    expect(part.type).toBe("tool-call");
    expect(part.toolCallId).toBe("call-1");
    expect(part.toolName).toBe("get_jobs");
    expect(part.result).toEqual({ status: "ok", preview: "3 jobs" });
    expect(part.isError).toBe(false);
  });

  it("marks a failed tool call as an error without inventing a result", () => {
    const message = toThreadMessageLike(
      assistant({
        parts: [{ kind: "tool", id: "call-1", name: "get_jobs", status: "error" }],
      }),
    );

    const part = (
      message.content as unknown as { isError?: boolean; result?: { status?: string } }[]
    )[0];
    expect(part.isError).toBe(true);
    expect(part.result?.status).toBe("error");
  });

  it("turns a pending approval into a question the runtime keeps open", () => {
    const message = toThreadMessageLike(
      assistant({
        parts: [
          {
            kind: "tool",
            id: "call-1",
            name: "add_job",
            status: "running",
            approval: { id: "apv_1", prompt: "Allow the assistant to add job?" },
          },
        ],
      }),
    );

    const part = (
      message.content as unknown as {
        approval?: { id?: string; prompt?: string };
        result?: unknown;
      }[]
    )[0];
    expect(part.approval).toEqual({ id: "apv_1", prompt: "Allow the assistant to add job?" });
    expect(part.result).toBeUndefined();
  });

  it("maps a source to a document citation", () => {
    const message = toThreadMessageLike(
      assistant({
        parts: [
          {
            kind: "source",
            id: "src-1",
            title: "get_jobs — JOB-1",
            filename: "get_jobs",
            mediaType: "application/json",
          },
        ],
      }),
    );

    expect(message.content).toEqual([
      {
        type: "source",
        sourceType: "document",
        id: "src-1",
        title: "get_jobs — JOB-1",
        mediaType: "application/json",
        filename: "get_jobs",
      },
    ]);
  });

  it("drops a part kind it does not know rather than rendering raw JSON", () => {
    const message = toThreadMessageLike(
      assistant({
        content: "still here",
        parts: [{ kind: "mystery" } as never],
      }),
    );

    expect(message.content).toEqual([{ type: "text", text: "still here" }]);
  });

  it("renders a notice as a system turn", () => {
    const message = toThreadMessageLike({
      id: "n-1",
      parentId: null,
      role: "notice",
      content: "**Studio status**",
    });

    expect(message.role).toBe("system");
  });

  it("carries the failure and the retry text so the transcript can offer both", () => {
    const error = {
      code: "mcp_unreachable",
      message: "The MCP server is unreachable.",
      retryable: true,
    };
    const message = toThreadMessageLike(
      assistant({ error, retryText: "list the jobs" }),
    );

    expect(message.status).toMatchObject({ type: "incomplete", reason: "error" });
    expect(message.metadata?.custom).toEqual({ error, retryText: "list the jobs" });
  });

  it("carries attachments on a user turn only", () => {
    const message = toThreadMessageLike({
      id: "m-1",
      parentId: null,
      role: "user",
      content: "look at this",
      attachments: [
        { id: "a-1", name: "notes.md", contentType: "text/markdown", size: 12 },
      ],
    });

    expect(message.attachments?.[0]).toMatchObject({
      id: "a-1",
      name: "notes.md",
      status: { type: "complete" },
    });
  });
});

describe("textOf", () => {
  it("reads the text parts of an appended message", () => {
    expect(
      textOf({
        content: [
          { type: "text", text: "first" },
          { type: "file", data: "x" },
          { type: "text", text: "second" },
        ] as never,
      }),
    ).toBe("first\nsecond");
  });

  it("passes a plain string through, trimmed", () => {
    expect(textOf({ content: "  hi  " })).toBe("hi");
  });
});
