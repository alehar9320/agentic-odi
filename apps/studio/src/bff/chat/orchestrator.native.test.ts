import { afterEach, describe, expect, it, vi } from "vitest";

import { MemoryLocalStore } from "../store/memoryStore";
import { LocalDataService } from "../data/localDataService";
import { LocalMemoryService } from "../memory/localMemoryService";
import { ChatOrchestrator, isDeterministicCommand } from "./orchestrator";
import type { NativeModelAdapter, NativeModelSession } from "./nativeModel";
import type { ChatMessage } from "../../types";
import type { RawSseEvent } from "../../api/sse";

function fakeSession(chunks: string[]): NativeModelSession {
  return {
    stream: async function* () {
      for (const chunk of chunks) {
        yield chunk;
      }
    },
    destroy: vi.fn(async () => {}),
  };
}

function fakeNative(overrides: Partial<NativeModelAdapter> = {}): NativeModelAdapter {
  return {
    availability: vi.fn(async () => "available" as const),
    create: vi.fn(async () => fakeSession(["native ", "prose"])),
    ...overrides,
  };
}

function makeBff(native: NativeModelAdapter | null = null) {
  const store = new MemoryLocalStore();
  const data = new LocalDataService(store);
  const memory = new LocalMemoryService(store);
  return {
    store,
    data,
    memory,
    orchestrator: new ChatOrchestrator(store, data, memory, native),
  };
}

function collectEvents() {
  const events: RawSseEvent[] = [];
  return { events, onEvent: (event: RawSseEvent) => events.push(event) };
}

function lastUserMessage(content: string, id = "u-1"): ChatMessage {
  return { id, parentId: null, role: "user", content };
}

/** No endpoint configured: an empty address is the browser-only case. */
function browserOnlyRequest(content: string, id = "u-1") {
  return {
    base_url: "",
    api_key: "",
    model: "",
    mcp_url: "http://localhost:8000/mcp",
    messages: [lastUserMessage(content, id)],
  };
}

const phases = (events: RawSseEvent[]) =>
  events.filter((e) => e.event === "status").map((e) => e.data.phase);
const messages = (events: RawSseEvent[]) =>
  events.filter((e) => e.event === "message").map((e) => String(e.data.content));

describe("isDeterministicCommand", () => {
  it("names exactly the commands the assistant can perform", () => {
    expect(isDeterministicCommand("add job Onboard customers")).toBe(true);
    expect(isDeterministicCommand("ADD OUTCOME Reduce setup time")).toBe(true);
    expect(isDeterministicCommand("remember the customer hates long setup")).toBe(true);
    expect(isDeterministicCommand("render the opportunity board")).toBe(true);
    expect(isDeterministicCommand("show me the board")).toBe(true);
    expect(isDeterministicCommand("how do I frame an outcome?")).toBe(false);
  });
});

describe("ChatOrchestrator browser-native provider", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("answers in prose from the browser model when no endpoint is configured", async () => {
    const native = fakeNative();
    const { orchestrator, memory } = makeBff(native);
    const { events, onEvent } = collectEvents();

    await orchestrator.stream(browserOnlyRequest("how do I frame an outcome?"), onEvent);

    expect(phases(events)).toContain("streaming");
    expect(messages(events)).toEqual(["native prose"]);
    expect(events.some((e) => e.event === "delta")).toBe(true);
    // Prose only: the native model cannot touch the canvas or the UI.
    expect(events.some((e) => e.event === "tool")).toBe(false);
    expect(events.some((e) => e.event === "tool_result")).toBe(false);
    expect(events.some((e) => e.event === "ui")).toBe(false);
    expect(events.some((e) => e.event === "canvas_dirty")).toBe(false);

    const { turns } = await memory.latestConversation();
    expect(turns.some((turn) => turn.role === "assistant" && turn.content === "native prose")).toBe(
      true,
    );
  });

  it("does not open a session for a model the browser would have to download", async () => {
    const native = fakeNative({ availability: vi.fn(async () => "downloadable" as const) });
    const { orchestrator } = makeBff(native);
    const { events, onEvent } = collectEvents();

    await orchestrator.stream(browserOnlyRequest("how do I frame an outcome?"), onEvent);

    expect(native.create).not.toHaveBeenCalled();
    expect(phases(events)).toContain("offline");
    expect(messages(events).some((content) => content.includes("canvas has"))).toBe(true);
  });

  it("demotes to the local answer when the model fails before it says anything", async () => {
    const native = fakeNative({
      create: vi.fn(async () => {
        throw new Error("model refused");
      }),
    });
    const { orchestrator } = makeBff(native);
    const { events, onEvent } = collectEvents();

    await orchestrator.stream(browserOnlyRequest("how do I frame an outcome?"), onEvent);

    expect(events.some((e) => e.event === "error")).toBe(false);
    expect(phases(events)).toContain("offline");
    expect(messages(events).some((content) => content.includes("canvas has"))).toBe(true);
  });

  it("reports a failure that happened after the model already spoke", async () => {
    const native = fakeNative({
      create: vi.fn(async () => ({
        stream: async function* () {
          yield "partial";
          throw new Error("connection dropped");
        },
        destroy: vi.fn(async () => {}),
      })),
    });
    const { orchestrator } = makeBff(native);
    const { events, onEvent } = collectEvents();

    await orchestrator.stream(browserOnlyRequest("how do I frame an outcome?"), onEvent);

    expect(events.some((e) => e.event === "error")).toBe(true);
    // The failure is reported, not papered over with a second, different answer.
    expect(messages(events).some((content) => content.includes("canvas has"))).toBe(false);
  });

  it("propagates an abort instead of trying a second provider", async () => {
    const controller = new AbortController();
    const native = fakeNative({
      create: vi.fn(async () => ({
        stream: async function* () {
          yield "partial";
          const abort = new Error("aborted");
          abort.name = "AbortError";
          throw abort;
        },
        destroy: vi.fn(async () => {}),
      })),
    });
    const { orchestrator } = makeBff(native);
    const { events, onEvent } = collectEvents();

    await expect(
      orchestrator.stream(browserOnlyRequest("how do I frame an outcome?"), onEvent, controller.signal),
    ).rejects.toMatchObject({ name: "AbortError" });
    expect(messages(events).some((content) => content.includes("canvas has"))).toBe(false);
  });

  it("lets a configured endpoint win over the browser model", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new TypeError("fetch failed");
      }),
    );
    const native = fakeNative();
    const { orchestrator } = makeBff(native);
    const { events, onEvent } = collectEvents();

    await orchestrator.stream(
      {
        ...browserOnlyRequest("how many jobs?"),
        base_url: "http://127.0.0.1:11434/v1",
        model: "qwen3:8b",
      },
      onEvent,
    );

    expect(native.create).not.toHaveBeenCalled();
    expect(phases(events)[0]).toBe("streaming");
  });

  it("runs a deterministic command even when the browser model is ready", async () => {
    const native = fakeNative();
    const { orchestrator, data } = makeBff(native);
    const { events, onEvent } = collectEvents();

    await orchestrator.stream(browserOnlyRequest("add job Onboard customers"), onEvent);

    expect(native.create).not.toHaveBeenCalled();
    expect(events.some((e) => e.event === "canvas_dirty")).toBe(true);
    expect(messages(events).some((content) => content.includes("Onboard customers"))).toBe(true);
    const canvas = await data.fetchCanvas();
    expect(canvas.jobs.map((job) => job.name)).toContain("Onboard customers");
  });

  it("stays deterministic when the browser has no model at all", async () => {
    const { orchestrator } = makeBff(null);
    const { events, onEvent } = collectEvents();

    await orchestrator.stream(browserOnlyRequest("how many jobs?"), onEvent);

    expect(phases(events)).toEqual(["offline"]);
    expect(messages(events).some((content) => content.includes("canvas has"))).toBe(true);
  });
});
