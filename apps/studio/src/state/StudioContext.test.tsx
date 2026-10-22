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

function route(input: RequestInfo | URL, init?: RequestInit): Response {
  const url = String(input);

  if (url === "/api/chat") {
    chatBody = JSON.parse(String(init?.body ?? "{}")) as Record<string, unknown>;
    return sse(
      'event: conversation\ndata: {"id":"c-2","title":"hello"}\n\n' +
        'event: memory\ndata: {"observation":{"id":"o-2","kind":"preference","text":"Prefers short updates.","data":{},"status":"suggested","confidence":0.7,"source_turn":null,"created_at":"2026-10-22T10:01:00+00:00","updated_at":"2026-10-22T10:01:00+00:00"}}\n\n' +
        'event: delta\ndata: {"text":"Hi"}\n\n' +
        'event: message\ndata: {"content":"Hi"}\n\n',
    );
  }
  if (url === "/api/config") {
    return json({
      defaults: { base_url: "http://llm", api_key: "k", model_name: "m", mcp_url: "http://mcp" },
    });
  }
  if (url.startsWith("/api/canvas")) {
    return json({ jobs: [], steps: [], outcomes: [], source: "local" });
  }
  if (url === "/api/connectors/catalog") {
    return json([]);
  }
  if (url === "/api/connectors") {
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
    return json({ healthy: true, message: "ok" });
  }
  return json({});
}

describe("StudioContext memory and resume", () => {
  beforeEach(() => {
    localStorage.clear();
    chatBody = null;
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
