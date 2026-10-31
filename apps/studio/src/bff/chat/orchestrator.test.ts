import { afterEach, describe, expect, it, vi } from "vitest";

import { MemoryLocalStore } from "../store/memoryStore";
import { LocalDataService } from "../data/localDataService";
import { LocalMemoryService } from "../memory/localMemoryService";
import { ChatOrchestrator } from "./orchestrator";
import type { ChatMessage } from "../../types";
import type { RawSseEvent } from "../../api/sse";

function makeBff() {
  const store = new MemoryLocalStore();
  const data = new LocalDataService(store);
  const memory = new LocalMemoryService(store);
  return new ChatOrchestrator(store, data, memory);
}

function collectEvents() {
  const events: RawSseEvent[] = [];
  return { events, onEvent: (event: RawSseEvent) => events.push(event) };
}

function lastUserMessage(content: string, id = "u-1"): ChatMessage {
  return { id, parentId: null, role: "user", content };
}

function streamRequest(content: string, id = "u-1") {
  return {
    base_url: "http://localhost:8001/v1",
    api_key: "local",
    model: "local",
    mcp_url: "http://localhost:8000/mcp",
    messages: [lastUserMessage(content, id)],
  };
}

describe("ChatOrchestrator deterministic mode", () => {
  it("answers about an empty canvas", async () => {
    const orchestrator = makeBff();
    const { events, onEvent } = collectEvents();
    await orchestrator.stream(streamRequest("how many jobs?"), onEvent);

    const messages = events.filter((e) => e.event === "message");
    expect(String(messages[messages.length - 1].data.content)).toContain("canvas has 0 jobs");
  });

  it("adds a job via the deterministic assistant", async () => {
    const orchestrator = makeBff();
    const { events, onEvent } = collectEvents();
    await orchestrator.stream(streamRequest("add job Onboard customers"), onEvent);

    const toolEvents = events.filter((e) => e.event === "tool");
    expect(toolEvents.some((e) => e.data.name === "create_job" && e.data.status === "running")).toBe(true);
    expect(toolEvents.some((e) => e.data.name === "create_job" && e.data.status === "ok")).toBe(true);
    const dirty = events.some((e) => e.event === "canvas_dirty");
    expect(dirty).toBe(true);
    const created = events.filter((e) => e.event === "message").map((e) => String(e.data.content));
    expect(created.some((c) => c.includes("Job \u201cOnboard customers\u201d created."))).toBe(true);
  });

  it("adds an outcome and computes opportunity score", async () => {
    const orchestrator = makeBff();
    const { events, onEvent } = collectEvents();
    await orchestrator.stream(streamRequest("add job Onboard customers"), onEvent);
    await orchestrator.stream(streamRequest("add outcome Reduce setup time importance 8 satisfaction 3"), onEvent);

    const created = events.filter((e) => e.event === "message").map((e) => String(e.data.content));
    expect(created.some((c) => c.includes("opportunity 13"))).toBe(true);
  });

  it("saves to memory and emits a memory event", async () => {
    const orchestrator = makeBff();
    const { events, onEvent } = collectEvents();
    await orchestrator.stream(streamRequest("remember the customer hates long setup"), onEvent);

    const memoryEvents = events.filter((e) => e.event === "memory");
    expect(memoryEvents.length).toBeGreaterThan(0);
    const confirmed = events.filter((e) => e.event === "tool" && e.data.name === "remember" && e.data.status === "ok");
    expect(confirmed.length).toBe(1);
  });

  it("renders a valid opportunity board", async () => {
    const orchestrator = makeBff();
    const { events, onEvent } = collectEvents();
    await orchestrator.stream(streamRequest("add job Onboard customers"), onEvent);
    await orchestrator.stream(streamRequest("add outcome Reduce setup time importance 8 satisfaction 3"), onEvent);
    await orchestrator.stream(streamRequest("render the opportunity board"), onEvent);

    const uiEvents = events.filter((e) => e.event === "ui");
    expect(uiEvents.length).toBe(1);
    const spec = uiEvents[0].data.spec as { type: string; props: { outcomes: unknown[] } };
    expect(spec.type).toBe("opportunity-board");
    expect(spec.props.outcomes).toHaveLength(1);
    expect(spec.props.outcomes[0]).toMatchObject({
      statement: "Reduce setup time",
      importance: 8,
      satisfaction: 3,
      opportunityScore: 13,
    });
  });

  it("persists user and assistant turns with ids", async () => {
    const orchestrator = makeBff();
    const { events, onEvent } = collectEvents();
    await orchestrator.stream(streamRequest("add job Onboard customers", "u-1"), onEvent);

    const conversation = events.find((e) => e.event === "conversation");
    expect(conversation).toBeDefined();
    expect(conversation!.data.id).toBeTruthy();
  });
});

describe("ChatOrchestrator provider choice", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  const firstPhase = (events: RawSseEvent[]) =>
    events.find((event) => event.event === "status")?.data.phase;

  it("calls an answer no model produced by its real name", async () => {
    const { events, onEvent } = collectEvents();
    await makeBff().stream(streamRequest("how many jobs?"), onEvent);

    expect(firstPhase(events)).toBe("offline");
  });

  it("routes a keyless model on the local network to the endpoint", async () => {
    // Ollama and LM Studio answer with no key at all. Treating them as
    // unconfigured made the browser write a local draft when a real model
    // was sitting on the same laptop.
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new TypeError("fetch failed");
      }),
    );
    const { events, onEvent } = collectEvents();
    await makeBff().stream(
      {
        ...streamRequest("how many jobs?"),
        base_url: "http://127.0.0.1:11434/v1",
        api_key: "",
        model: "qwen3:8b",
      },
      onEvent,
    );

    expect(firstPhase(events)).toBe("streaming");
    expect(events.some((event) => event.event === "error")).toBe(true);
  });
});
