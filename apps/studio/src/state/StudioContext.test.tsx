import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { StudioProvider, useStudio } from "./StudioContext";

const CONVERSATION = {
  id: "c-1",
  title: "I own activation.",
  created_at: "2026-10-22T10:00:00+00:00",
  updated_at: "2026-10-22T10:00:00+00:00",
};

const OBSERVATION = {
  id: "o-1",
  kind: "career",
  text: "Accountable for activation.",
  data: {},
  status: "confirmed",
  confidence: 0.9,
  source_turn: 1,
  created_at: "2026-10-22T10:00:00+00:00",
  updated_at: "2026-10-22T10:00:00+00:00",
};

function json(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

function sse(body: string): Response {
  return new Response(body, {
    status: 200,
    headers: { "Content-Type": "text/event-stream" },
  });
}

let chatBody: Record<string, unknown> | null = null;

const DEFAULT_CHAT_STREAM =
  'event: conversation\ndata: {"id":"c-2","title":"hello"}\n\n' +
  'event: memory\ndata: {"observation":{"id":"o-2","kind":"preference","text":"Prefers short updates.","data":{},"status":"suggested","confidence":0.7,"source_turn":null,"created_at":"2026-10-22T10:01:00+00:00","updated_at":"2026-10-22T10:01:00+00:00"}}\n\n' +
  'event: delta\ndata: {"text":"Hi"}\n\n' +
  'event: message\ndata: {"content":"Hi"}\n\n';

let chatStream: string | null = null;
let canvasFails = false;
let chatFailure: Error | null = null;
let connectorFetches = 0;
let llmHealthFetches = 0;

function route(input: RequestInfo | URL, init?: RequestInit): Response {
  const url = String(input);

  if (url === "/api/chat") {
    chatBody = JSON.parse(String(init?.body ?? "{}")) as Record<string, unknown>;
    if (chatFailure) {
      throw chatFailure;
    }
    return sse(chatStream ?? DEFAULT_CHAT_STREAM);
  }
  if (url === "/api/config") {
    return json({
      defaults: { base_url: "http://llm", api_key: "k", model_name: "m", mcp_url: "http://mcp" },
    });
  }
  if (url.startsWith("/api/canvas")) {
    if (canvasFails) {
      return new Response(JSON.stringify({ error: { code: "mcp_unreachable", message: "The MCP server is unreachable.", retryable: true } }), {
        status: 502,
        headers: { "Content-Type": "application/json" },
      });
    }
    return json({ jobs: [], steps: [], outcomes: [], source: "local" });
  }
  if (url === "/api/connectors/catalog") {
    return json([]);
  }
  if (url === "/api/connectors") {
    connectorFetches += 1;
    return json([]);
  }
  if (url === "/api/memory/observations") {
    return json({ observations: [OBSERVATION] });
  }
  if (url === "/api/conversations/latest") {
    return json({
      conversation: CONVERSATION,
      turns: [
        {
          id: 1,
          conversation_id: "c-1",
          role: "user",
          content: "I own activation.",
          created_at: "2026-10-22T10:00:00+00:00",
        },
        {
          id: 2,
          conversation_id: "c-1",
          role: "assistant",
          content: "Tell me more.",
          created_at: "2026-10-22T10:00:01+00:00",
        },
      ],
    });
  }
  if (url === "/api/conversations") {
    return json({
      conversation: {
        id: "c-new",
        title: "",
        created_at: "2026-10-22T10:00:00+00:00",
        updated_at: "2026-10-22T10:00:00+00:00",
      },
    });
  }
  if (url === "/api/health/mcp") {
    return json({ reachable: true });
  }
  if (url === "/api/health/llm") {
    llmHealthFetches += 1;
    return json({ healthy: true, message: "ok" });
  }
  return json({});
}

describe("StudioContext memory and resume", () => {
  beforeEach(() => {
    localStorage.clear();
    chatBody = null;
    chatStream = null;
    chatFailure = null;
    canvasFails = false;
    connectorFetches = 0;
    llmHealthFetches = 0;
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => route(input, init)));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("resumes the latest conversation and loads what it learned", async () => {
    const { result } = renderHook(() => useStudio(), { wrapper: StudioProvider });

    await waitFor(() => expect(result.current.conversationId).toBe("c-1"));
    expect(result.current.messages.map((message) => message.content)).toEqual([
      "I own activation.",
      "Tell me more.",
    ]);
    expect(result.current.memory.map((item) => item.text)).toEqual([
      "Accountable for activation.",
    ]);
  });

  it("sends the conversation id and applies memory events", async () => {
    const { result } = renderHook(() => useStudio(), { wrapper: StudioProvider });
    await waitFor(() => expect(result.current.conversationId).toBe("c-1"));

    await act(async () => {
      await result.current.sendMessage("hello");
    });

    expect(chatBody?.conversation_id).toBe("c-1");
    expect(result.current.conversationId).toBe("c-2");
    expect(result.current.memory.map((item) => item.text)).toContain("Prefers short updates.");
    expect(result.current.messages.at(-1)?.content).toBe("Hi");
  });

  it("clears the thread and starts a fresh conversation", async () => {
    const { result } = renderHook(() => useStudio(), { wrapper: StudioProvider });
    await waitFor(() => expect(result.current.conversationId).toBe("c-1"));

    act(() => result.current.clearChat());

    expect(result.current.messages).toEqual([]);
    await waitFor(() => expect(result.current.conversationId).toBe("c-new"));
  });
});

describe("StudioContext failures", () => {
  beforeEach(() => {
    localStorage.clear();
    chatBody = null;
    chatStream = null;
    chatFailure = null;
    canvasFails = false;
    connectorFetches = 0;
    llmHealthFetches = 0;
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => route(input, init)));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("keeps the question and the failed turn when the stream reports an error", async () => {
    chatStream =
      'event: error\ndata: {"error":{"code":"mcp_unreachable","message":"MCP server unreachable","retryable":true,"request_id":"req-1"}}\n\n';
    const { result } = renderHook(() => useStudio(), { wrapper: StudioProvider });
    await waitFor(() => expect(result.current.conversationId).toBe("c-1"));

    await act(async () => {
      await result.current.sendMessage("list the jobs");
    });

    const messages = result.current.messages;
    expect(messages.some((message) => message.role === "user" && message.content === "list the jobs")).toBe(true);
    const last = messages.at(-1);
    expect(last?.role).toBe("assistant");
    expect(last?.error?.code).toBe("mcp_unreachable");
    expect(last?.retryText).toBe("list the jobs");
  });

  it("keeps the question when the request itself fails", async () => {
    chatFailure = new Error("network down");
    const { result } = renderHook(() => useStudio(), { wrapper: StudioProvider });
    await waitFor(() => expect(result.current.conversationId).toBe("c-1"));

    await act(async () => {
      await result.current.sendMessage("list the jobs");
    });

    const messages = result.current.messages;
    expect(messages.some((message) => message.role === "user" && message.content === "list the jobs")).toBe(true);
    expect(messages.at(-1)?.error?.code).toBe("internal");
  });

  it("reports a stream that ends without a message as an internal failure", async () => {
    chatStream = 'event: status\ndata: {"phase":"model"}\n\n';
    const { result } = renderHook(() => useStudio(), { wrapper: StudioProvider });
    await waitFor(() => expect(result.current.conversationId).toBe("c-1"));

    await act(async () => {
      await result.current.sendMessage("list the jobs");
    });

    expect(result.current.messages.at(-1)?.error?.code).toBe("internal");
  });

  it("keeps a connector failure as a notice and refreshes the connectors", async () => {
    chatStream =
      'event: connector\ndata: {"status":"error","error":"preset not found"}\n\n' +
      'event: message\ndata: {"content":"Sorry."}\n\n';
    const { result } = renderHook(() => useStudio(), { wrapper: StudioProvider });
    await waitFor(() => expect(result.current.conversationId).toBe("c-1"));
    const before = connectorFetches;

    await act(async () => {
      await result.current.sendMessage("add the connector");
    });

    expect(result.current.messages.some((message) => message.role === "notice")).toBe(true);
    expect(connectorFetches).toBeGreaterThan(before);
  });
});

describe("StudioContext health polling", () => {
  beforeEach(() => {
    localStorage.clear();
    chatBody = null;
    chatStream = null;
    chatFailure = null;
    canvasFails = false;
    connectorFetches = 0;
    llmHealthFetches = 0;
    vi.useFakeTimers();
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => route(input, init)));
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("re-probes the model every 30 seconds and when the window comes back", async () => {
    const { result } = renderHook(() => useStudio(), { wrapper: StudioProvider });
    await act(async () => {
      await Promise.resolve();
    });
    const initial = llmHealthFetches;

    await act(async () => {
      vi.advanceTimersByTime(30_000);
    });
    expect(llmHealthFetches).toBeGreaterThan(initial);

    const afterInterval = llmHealthFetches;
    await act(async () => {
      document.dispatchEvent(new Event("visibilitychange"));
    });
    expect(llmHealthFetches).toBeGreaterThan(afterInterval);
    expect(result.current.llmHealth.healthy).toBe(true);
  });
});

describe("StudioContext canvas state", () => {
  beforeEach(() => {
    localStorage.clear();
    chatBody = null;
    chatStream = null;
    chatFailure = null;
    canvasFails = false;
    connectorFetches = 0;
    llmHealthFetches = 0;
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => route(input, init)));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("reports a failed canvas as an error state, not as an empty canvas", async () => {
    canvasFails = true;
    const { result } = renderHook(() => useStudio(), { wrapper: StudioProvider });

    await waitFor(() => expect(result.current.canvasState.kind).toBe("error"));
    expect(result.current.canvasError?.code).toBe("mcp_unreachable");
    expect(result.current.canvasLoading).toBe(false);
  });

  it("reports a canvas with no work as empty, not as ready", async () => {
    const { result } = renderHook(() => useStudio(), { wrapper: StudioProvider });

    await waitFor(() => expect(result.current.canvasState.kind).toBe("empty"));
    expect(result.current.canvasError).toBeNull();
  });
});
