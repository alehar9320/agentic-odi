import type { AppendMessage } from "@assistant-ui/react";
import { describe, expect, it } from "vitest";

import type { ChatMessage } from "../types";
import {
  metaOf,
  textOf,
  toThreadMessage,
  toThreadMessages,
  turnFromAppend,
  type ThreadContext,
} from "./thread";

const idle: ThreadContext = { streaming: false, phase: null, offline: false };

function turn(messages: ChatMessage[], index: number, ctx: ThreadContext = idle) {
  return toThreadMessage(messages[index], index, messages.length - 1, ctx);
}

describe("toThreadMessage", () => {
  it("keeps a turn's id, and gives a turn without one a positional id", () => {
    expect(turn([{ id: "turn-a", role: "user", content: "hi" }], 0).id).toBe("turn-a");
    expect(turn([{ role: "user", content: "hi" }], 0).id).toBe("turn-0");
  });

  it("maps a local notice to a system turn with nothing to stream", () => {
    const message = turn([{ role: "notice", content: "**2 jobs** on the canvas." }], 0);

    expect(message.role).toBe("system");
    expect(message.status).toBeUndefined();
  });

  it("keeps prose and surfaces in the agent's order", () => {
    const message = turn(
      [
        {
          role: "assistant",
          content: "Before.After.",
          parts: [
            { kind: "text", text: "Before." },
            { kind: "ui", id: "ui-1", node: { type: "outcome-card", props: {} } as never },
            { kind: "text", text: "After." },
          ],
        },
      ],
      0,
    );

    expect(message.content).toEqual([
      { type: "text", text: "Before." },
      { type: "data", name: "ui", id: "ui-1", data: expect.objectContaining({ id: "ui-1" }) },
      { type: "text", text: "After." },
    ]);
  });

  it("falls back to the joined prose for a turn with no parts", () => {
    const message = turn([{ role: "assistant", content: "**Scored** three outcomes." }], 0);

    expect(message.content).toEqual([{ type: "text", text: "**Scored** three outcomes." }]);
  });

  it("calls the newest turn running while it streams, and history settled", () => {
    const messages: ChatMessage[] = [
      { role: "user", content: "first" },
      { role: "assistant", content: "First answer." },
      { role: "user", content: "second" },
      { role: "assistant", content: "Still writ" },
    ];

    const ctx = { streaming: true, phase: "model", offline: false };

    expect(turn(messages, 3, ctx).status).toEqual({ type: "running" });
    expect(turn(messages, 1, ctx).status).toEqual({ type: "complete", reason: "stop" });
  });

  it("marks a stopped turn cancelled and a failed turn errored", () => {
    const stopped = turn([{ role: "assistant", content: "So far", stopped: true }], 0);
    const failed = turn(
      [
        {
          role: "assistant",
          content: "",
          error: {
            code: "mcp_unreachable",
            message: "No MCP.",
            retryable: true,
          },
        },
      ],
      0,
    );

    expect(stopped.status).toEqual({ type: "incomplete", reason: "cancelled" });
    expect(failed.status).toEqual({ type: "incomplete", reason: "error" });
  });

  it("carries the studio's own fields so the turn still renders as itself", () => {
    const tools = [{ id: "get_jobs-0", name: "get_jobs", status: "ok" as const, startedAt: 0 }];
    const messages: ChatMessage[] = [
      { id: "q", role: "user", content: "list the jobs" },
      {
        id: "a",
        role: "assistant",
        content: "Two jobs.",
        tools,
        stopped: true,
        retryText: "list the jobs",
        retryAttachments: [{ name: "shot.png", media_type: "image/png", data: "AA==" }],
      },
    ];

    const meta = metaOf(turn(messages, 1));

    expect(meta.tools).toEqual(tools);
    expect(meta.stopped).toBe(true);
    expect(meta.retryText).toBe("list the jobs");
    expect(meta.retryAttachments?.[0].name).toBe("shot.png");
  });

  it("tells only the newest turn what the run is doing right now", () => {
    const messages: ChatMessage[] = [
      { role: "assistant", content: "Old answer." },
      { role: "assistant", content: "" },
    ];
    const ctx = { streaming: true, phase: "mcp_tools", offline: true };

    expect(metaOf(turn(messages, 1, ctx)).phase).toBe("mcp_tools");
    expect(metaOf(turn(messages, 1, ctx)).offline).toBe(true);
    expect(metaOf(turn(messages, 0, ctx)).phase).toBeUndefined();
    expect(metaOf(turn(messages, 0, ctx)).offline).toBeUndefined();
  });

  it("sends an attachment as bytes the runtime can render", () => {
    const message = turn(
      [
        {
          role: "user",
          content: "What is broken?",
          attachments: [
            { name: "shot.png", media_type: "image/png", data: "AQID" },
            { name: "logs.txt", media_type: "text/plain", data: "Ym9vbQ==" },
          ],
        },
      ],
      0,
    );

    expect(message.content).toEqual([
      { type: "text", text: "What is broken?" },
      {
        type: "image",
        id: "file-0",
        image: "data:image/png;base64,AQID",
        filename: "shot.png",
      },
      {
        type: "file",
        id: "file-1",
        filename: "logs.txt",
        data: "Ym9vbQ==",
        mimeType: "text/plain",
      },
    ]);
  });
});

describe("toThreadMessages", () => {
  it("maps every turn in order", () => {
    const messages: ChatMessage[] = [
      { role: "user", content: "one" },
      { role: "assistant", content: "two" },
      { role: "notice", content: "three" },
    ];

    expect(toThreadMessages(messages, idle).map((message) => message.role)).toEqual([
      "user",
      "assistant",
      "system",
    ]);
  });
});

describe("textOf", () => {
  it("reads the prose out of a runtime message, ignoring any surface", () => {
    const message = turn(
      [
        {
          role: "assistant",
          content: "Before.After.",
          parts: [
            { kind: "text", text: "Before." },
            { kind: "ui", id: "ui-1", node: { type: "outcome-card", props: {} } as never },
            { kind: "text", text: "After." },
          ],
        },
      ],
      0,
    );

    expect(
      textOf({ content: message.content as Parameters<typeof textOf>[0]["content"] }),
    ).toBe("Before.After.");
  });
});

describe("turnFromAppend", () => {
  function append(parts: unknown[]): AppendMessage {
    return {
      role: "user",
      content: parts,
      createdAt: new Date(),
      parentId: null,
      sourceId: null,
      runConfig: undefined,
    } as unknown as AppendMessage;
  }

  it("recovers the question and the image bytes the runtime decoded", () => {
    const { text, attachments } = turnFromAppend(
      append([
        { type: "text", text: "What is broken here?" },
        { type: "image", image: "data:image/png;base64,AQID", filename: "shot.png" },
      ]),
    );

    expect(text).toBe("What is broken here?");
    expect(attachments).toEqual([
      { name: "shot.png", media_type: "image/png", data: "AQID" },
    ]);
  });

  it("recovers a text file as the bytes the sidecar inlines", () => {
    const { attachments } = turnFromAppend(
      append([
        { type: "text", text: "" },
        { type: "file", filename: "logs.txt", data: "Ym9vbQ==", mimeType: "text/plain" },
      ]),
    );

    expect(attachments).toEqual([
      { name: "logs.txt", media_type: "text/plain", data: "Ym9vbQ==" },
    ]);
  });

  it("drops an image whose source is not readable bytes", () => {
    const { attachments } = turnFromAppend(
      append([
        { type: "text", text: "look" },
        { type: "image", image: "https://example.com/shot.png" },
      ]),
    );

    expect(attachments).toEqual([]);
  });
});
