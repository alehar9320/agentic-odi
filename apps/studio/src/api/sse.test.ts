import { describe, expect, it } from "vitest";

import { createSseParser } from "./sse";

describe("createSseParser", () => {
  it("parses complete frames into typed events", () => {
    const parser = createSseParser();

    const events = parser.push(
      'event: delta\ndata: {"text":"hi"}\n\nevent: message\ndata: {"content":"hi"}\n\n',
    );

    expect(events).toEqual([
      { event: "delta", data: { text: "hi" } },
      { event: "message", data: { content: "hi" } },
    ]);
  });

  it("buffers frames that are split across chunks", () => {
    const parser = createSseParser();

    expect(parser.push('event: status\ndata: {"ph')).toEqual([]);
    expect(parser.push('ase":"model"}\n\n')).toEqual([
      { event: "status", data: { phase: "model" } },
    ]);
  });

  it("parses tool and canvas_dirty frames", () => {
    const parser = createSseParser();

    const events = parser.push(
      'event: tool\ndata: {"name":"get_jobs","status":"start"}\n\nevent: canvas_dirty\ndata: {"value":true}\n\n',
    );

    expect(events).toEqual([
      { event: "tool", data: { name: "get_jobs", status: "start" } },
      { event: "canvas_dirty", data: { value: true } },
    ]);
  });

  it("parses connector frames", () => {
    const parser = createSseParser();

    const events = parser.push('event: connector\ndata: {"action":"registered","name":"gong"}\n\n');

    expect(events).toEqual([{ event: "connector", data: { action: "registered", name: "gong" } }]);
  });
});
