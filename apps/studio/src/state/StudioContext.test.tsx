import { act, render, renderHook, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
// The browser BFF is the first-run answer path, and it lives in IndexedDB.
import "fake-indexeddb/auto";

import { SESSION_KEY } from "../lib/session";
import { queuedUserMessage } from "../assistant/queue";
import {
  CountedStudio,
  expectRenderBudget,
  getCounts,
  resetCounts,
  streamOfDeltas,
  typeIntoComposer,
} from "../test/renderCounts";
import type { StudioContextValue } from "./StudioContext";
import { StudioProvider, useStudio } from "./StudioContext";
import { PROBE_BASE_MS, PROBE_JITTER, PROBE_SETTINGS_DEBOUNCE_MS } from "./scheduleProbe";

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
let chatAttempts = 0;

const DEFAULT_CHAT_STREAM =
  'event: conversation\ndata: {"id":"c-2","title":"hello"}\n\n' +
  'event: memory\ndata: {"observation":{"id":"o-2","kind":"preference","text":"Prefers short updates.","data":{},"status":"suggested","confidence":0.7,"source_turn":null,"created_at":"2026-10-22T10:01:00+00:00","updated_at":"2026-10-22T10:01:00+00:00"}}\n\n' +
  'event: delta\ndata: {"text":"Hi"}\n\n' +
  'event: message\ndata: {"content":"Hi"}\n\n';

let chatStream: string | null = null;
let canvasFails = false;
/** Extra records the canvas route serves; empty keeps every other test as-is. */
let canvasRecords: Record<string, unknown> = {};
let bootCorrupt = false;
let chatAborts = false;
let chatFailure: Error | null = null;
let chatHangs = false;
let releaseChat: (() => void) | null = null;
let connectorFetches = 0;
let llmHealthFetches = 0;
let llmUnhealthy = false;
let signalFetches = 0;
let configHangs = false;
let configAborts = 0;
let catalogFetches = 0;
let featuredFetches = 0;
let capabilityProbes = 0;
let approvalCalls: Record<string, unknown>[] = [];
let headPatches: Record<string, unknown>[] = [];
let conversationCreates = 0;

// The follow-up queue (#410) needs a turn that stays in flight so later sends
// actually line up behind it: /api/chat then returns a stream the test closes
// (respond) or breaks (abort — the same way aborting the fetch signal would).
type GatedTurn = {
  body: Record<string, unknown>;
  aborted: boolean;
  respond: (events: string) => void;
  abort: () => void;
};
let gateChats = false;
let gatedTurns: GatedTurn[] = [];

function gatedChatResponse(
  body: Record<string, unknown>,
  signal?: AbortSignal | null,
): Response {
  const encoder = new TextEncoder();
  let streamController: ReadableStreamDefaultController<Uint8Array> | undefined;
  const turn: GatedTurn = {
    body,
    aborted: false,
    respond: (events) => {
      streamController?.enqueue(encoder.encode(events));
      streamController?.close();
    },
    abort: () => {
      turn.aborted = true;
      const error = new Error("The user aborted a request.");
      error.name = "AbortError";
      streamController?.error(error);
    },
  };
  signal?.addEventListener("abort", turn.abort, { once: true });
  gatedTurns.push(turn);
  return new Response(
    new ReadableStream<Uint8Array>({
      start(controller) {
        streamController = controller;
      },
    }),
    { status: 200, headers: { "Content-Type": "text/event-stream" } },
  );
}

function route(
  input: RequestInfo | URL,
  init?: RequestInit,
  configFails = false,
): Response | Promise<Response> {
  const url = String(input);

  if (url === "/api/chat") {
    chatBody = JSON.parse(String(init?.body ?? "{}")) as Record<string, unknown>;
    chatAttempts += 1;
    if (chatAborts) {
      const error = new Error("The user aborted a request.");
      error.name = "AbortError";
      throw error;
    }
    if (chatFailure) {
      throw chatFailure;
    }
    if (chatHangs) {
      // A reply still in the air. A browser's fetch rejects on abort, so the
      // studio's own cancel path can be exercised against this stub.
      const signal = init?.signal;
      return new Promise<Response>((resolve, reject) => {
        releaseChat = () => resolve(sse(chatStream ?? DEFAULT_CHAT_STREAM));
        signal?.addEventListener("abort", () => {
          const error = new Error("The user aborted a request.");
          error.name = "AbortError";
          reject(error);
        });
      });
    }
    if (gateChats) {
      return gatedChatResponse(chatBody as Record<string, unknown>, init?.signal);
    }
    return sse(chatStream ?? DEFAULT_CHAT_STREAM);
  }
  if (url === "/api/config") {
    if (configHangs) {
      // A slow laptop, a cold sidecar: the request is in the air and nothing is
      // known yet. This is the state a first-time visitor actually sits in. A
      // caller that bounds the request hands us a signal; when it fires, the
      // request fails the way a real aborted fetch does.
      return new Promise<Response>((_resolve, reject) => {
        init?.signal?.addEventListener("abort", () => {
          configAborts += 1;
          const error = new Error("The operation was aborted.");
          error.name = "AbortError";
          reject(error);
        });
      });
    }
    if (bootCorrupt) {
      return new Response(
        JSON.stringify({
          error: {
            code: "store_corrupt",
            message:
              "Your database failed its integrity check: /home/me/.odi.db. " +
              "Last backup: 06:14 (odi-20260102T061400Z.db).",
            detail: "database disk image is malformed",
            suggestion: "Restore odi-20260102T061400Z.db over odi.db, then restart.",
            retryable: false,
          },
        }),
        { status: 503, headers: { "Content-Type": "application/json" } },
      );
    }
    if (configFails) {
      throw new TypeError("fetch failed");
    }
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
    return json({ jobs: [], steps: [], outcomes: [], source: "local", ...canvasRecords });
  }
  if (url === "/api/connectors/catalog") {
    catalogFetches += 1;
    return json([]);
  }
  if (url.startsWith("/api/marketplace/servers")) {
    return json({ listings: [], areas: {}, cached: false, types: [{ id: "mcp", label: "MCP servers", available: true }] });
  }
  if (url.startsWith("/api/marketplace/featured")) {
    featuredFetches += 1;
    return json({ listings: [], areas: {}, cached: false, types: [] });
  }
  if (url === "/api/capabilities") {
    capabilityProbes += 1;
    return json({ capabilities: [] });
  }
  if (url === "/api/connectors") {
    if (init?.method === "POST") {
      return json({ ok: true, name: "gong" });
    }
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
  if (url.startsWith("/api/approvals/")) {
    approvalCalls.push(JSON.parse(String(init?.body ?? "{}")) as Record<string, unknown>);
    return json({ ok: true, id: url.split("/").pop() });
  }
  if (init?.method === "PATCH" && url.startsWith("/api/conversations/")) {
    headPatches.push(JSON.parse(String(init?.body ?? "{}")) as Record<string, unknown>);
    return json({ conversation: CONVERSATION });
  }
  if (url === "/api/conversations/c-1/tree") {
    return json({
      conversation: CONVERSATION,
      messages: [
        {
          id: "t-1",
          parent_id: null,
          role: "user",
          content: "I own activation.",
          created_at: "2026-10-22T10:00:00+00:00",
        },
        {
          id: "t-2",
          parent_id: "t-1",
          role: "assistant",
          content: "Tell me more.",
          created_at: "2026-10-22T10:00:01+00:00",
        },
      ],
      head_id: "t-2",
    });
  }
  if (url === "/api/conversations") {
    if (init?.method === "POST") {
      conversationCreates += 1;
      return json({
        conversation: {
          id: "c-new",
          title: "",
          created_at: "2026-10-22T10:00:00+00:00",
          updated_at: "2026-10-22T10:00:00+00:00",
        },
      });
    }
    return json({
      conversations: [
        {
          id: "c-1",
          title: "I own activation.",
          created_at: "2026-10-22T10:00:00+00:00",
          updated_at: "2026-10-22T10:00:00+00:00",
          head_id: "t-2",
          turn_count: 2,
        },
        {
          id: "c-old",
          title: "Price the churn spike",
          created_at: "2026-10-20T10:00:00+00:00",
          updated_at: "2026-10-20T10:00:00+00:00",
          head_id: null,
          turn_count: 1,
        },
      ],
    });
  }
  if (url === "/api/health/mcp") {
    return json({ reachable: true });
  }
  if (url === "/api/health/llm") {
    llmHealthFetches += 1;
    return json(
      llmUnhealthy
        ? { healthy: false, message: "connection refused" }
        : { healthy: true, message: "ok" },
    );
  }
  if (url.startsWith("/api/signals/unread-count")) {
    return json({ count: 0 });
  }
  if (url.startsWith("/api/signals")) {
    signalFetches += 1;
    return json([]);
  }
  return json({});
}

describe("StudioContext memory and resume", () => {
  beforeEach(() => {
    localStorage.clear();
    chatBody = null;
    chatStream = null;
    chatFailure = null;
    chatAttempts = 0;
    chatAborts = false;
    canvasFails = false;
    bootCorrupt = false;
    connectorFetches = 0;
    llmHealthFetches = 0;
    approvalCalls = [];
    headPatches = [];
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => route(input, init)));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("restores the focused subject from the previous session", () => {
    localStorage.setItem(
      SESSION_KEY,
      JSON.stringify({ job_id: null, step_id: null, outcome_id: "O-9" }),
    );

    const { result } = renderHook(() => useStudio(), { wrapper: StudioProvider });

    expect(result.current.focusedSubject).toEqual({ kind: "outcome", id: "O-9" });
  });

  it("remembers the subject the user navigates to", () => {
    const { result } = renderHook(() => useStudio(), { wrapper: StudioProvider });

    act(() => {
      result.current.focusSubject("job", "JOB-7");
    });

    expect(result.current.focusedSubject).toEqual({ kind: "job", id: "JOB-7" });
    expect(JSON.parse(localStorage.getItem(SESSION_KEY) ?? "{}")).toEqual({
      job_id: "JOB-7",
      step_id: null,
      outcome_id: null,
    });
  });

  it("starts clean when the stored session is unreadable", () => {
    localStorage.setItem(SESSION_KEY, "broken");

    const { result } = renderHook(() => useStudio(), { wrapper: StudioProvider });

    expect(result.current.focusedSubject).toBeNull();
  });

  it("sends the visible conversation path as model context", async () => {
    const { result } = renderHook(() => useStudio(), { wrapper: StudioProvider });
    await waitFor(() => expect(result.current.messages).toHaveLength(2));

    await act(async () => {
      await result.current.sendMessage("What should I do next?");
    });

    expect(chatBody?.messages).toEqual([
      { id: "t-1", parent_id: null, role: "user", content: "I own activation." },
      { id: "t-2", parent_id: "t-1", role: "assistant", content: "Tell me more." },
      expect.objectContaining({ role: "user", content: "What should I do next?", parent_id: "t-2" }),
    ]);
  });

  it("regenerates an answer from its existing user turn without duplicating it", async () => {
    const { result } = renderHook(() => useStudio(), { wrapper: StudioProvider });
    await waitFor(() => expect(result.current.messages).toHaveLength(2));

    await act(async () => {
      await result.current.regenerateFrom("t-1");
    });

    expect(chatBody?.messages).toEqual([
      { id: "t-1", parent_id: null, role: "user", content: "I own activation." },
    ]);
    expect(result.current.messages.map((message) => message.content)).toEqual([
      "I own activation.",
      "Hi",
    ]);
    expect(result.current.messages.filter((message) => message.role === "user")).toHaveLength(1);
    expect(result.current.messages.at(-1)).toMatchObject({ role: "assistant", parentId: "t-1" });
  });

  it("edits a user turn by replacing it at its original parent", async () => {
    const { result } = renderHook(() => useStudio(), { wrapper: StudioProvider });
    await waitFor(() => expect(result.current.messages).toHaveLength(2));

    await act(async () => {
      await result.current.editFrom("t-1", "I own onboarding.");
    });

    expect(chatBody?.messages).toEqual([
      expect.objectContaining({ role: "user", content: "I own onboarding.", parent_id: null }),
    ]);
    expect(result.current.messages.map((message) => message.content)).toEqual([
      "I own onboarding.",
      "Hi",
    ]);
    expect(result.current.messages[0].parentId).toBeNull();
  });

  it("serializes attachments with the sidecar's snake-case fields", async () => {
    const { result } = renderHook(() => useStudio(), { wrapper: StudioProvider });
    await waitFor(() => expect(result.current.conversationId).toBe("c-1"));

    await act(async () => {
      await result.current.sendMessage("Read this", [
        {
          id: "file-1",
          name: "notes.md",
          contentType: "text/markdown",
          size: 12,
          text: "Useful context",
          dataUrl: "data:image/png;base64,AAAA",
        },
      ]);
    });

    expect(chatBody?.attachments).toEqual([
      {
        name: "notes.md",
        content_type: "text/markdown",
        size: 12,
        text: "Useful context",
        data_url: "data:image/png;base64,AAAA",
      },
    ]);
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

  it("loads the history list on boot, newest first", async () => {
    const { result } = renderHook(() => useStudio(), { wrapper: StudioProvider });

    await waitFor(() => expect(result.current.conversations).toHaveLength(2));
    expect(result.current.conversations.map((conversation) => conversation.id)).toEqual([
      "c-1",
      "c-old",
    ]);
    expect(result.current.conversations[0].title).toBe("I own activation.");
  });

  it("opens a past conversation by loading its turns", async () => {
    const { result } = renderHook(() => useStudio(), { wrapper: StudioProvider });
    await waitFor(() => expect(result.current.conversationId).toBe("c-1"));

    await act(async () => {
      await result.current.openConversation("c-1");
    });

    expect(result.current.conversationId).toBe("c-1");
    expect(result.current.messages.map((message) => message.content)).toEqual([
      "I own activation.",
      "Tell me more.",
    ]);
  });

  it("toasts after creating a job and recording an outcome", async () => {
    const { result } = renderHook(() => useStudio(), { wrapper: StudioProvider });
    await waitFor(() => expect(result.current.conversationId).toBe("c-1"));

    await act(async () => {
      await result.current.createJob({ name: "New job" });
    });
    expect(result.current.toasts.map((toast) => toast.message)).toContain("Job created: New job");

    await act(async () => {
      await result.current.addOutcome({
        job_id: "JOB-1",
        statement: "Minimize the time it takes to ship",
        importance: 8,
        satisfaction: 3,
      });
    });
    expect(result.current.toasts.map((toast) => toast.message)).toContain(
      "Outcome captured successfully!",
    );
  });

  it("confirms a connector was added", async () => {
    const { result } = renderHook(() => useStudio(), { wrapper: StudioProvider });
    await waitFor(() => expect(result.current.conversationId).toBe("c-1"));

    await act(async () => {
      await result.current.addConnector({
        name: "gong",
        url: "http://localhost:9000/mcp",
      });
    });

    expect(result.current.toasts).toContainEqual(
      expect.objectContaining({ kind: "success", message: "Added connector gong" }),
    );
  });

  it("persists a saved opportunity thesis", async () => {
    const { result } = renderHook(() => useStudio(), { wrapper: StudioProvider });
    await waitFor(() => expect(result.current.conversationId).toBe("c-1"));

    act(() => {
      result.current.saveThesis({
        outcome_id: "O-1",
        job_id: "JOB-1",
        statement: "Minimize the time to ship when the build is green.",
        importance: 9,
        satisfaction: 3,
        opportunity_score: 15,
        rationale: "Shipping fast is the bet.",
      });
    });

    expect(result.current.theses).toHaveLength(1);
    const stored = JSON.parse(localStorage.getItem("studio.theses") ?? "[]");
    expect(stored[0]).toMatchObject({
      outcome_id: "O-1",
      rationale: "Shipping fast is the bet.",
    });
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
    chatAttempts = 0;
    chatAborts = false;
    canvasFails = false;
    bootCorrupt = false;
    connectorFetches = 0;
    llmHealthFetches = 0;
    approvalCalls = [];
    headPatches = [];
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

describe("StudioContext first run in a browser with no server", () => {
  let configFails: boolean;

  beforeEach(() => {
    configFails = true;
    configHangs = false;
    llmUnhealthy = false;
    localStorage.clear();
    chatBody = null;
    chatStream = null;
    chatFailure = null;
    chatAttempts = 0;
    chatAborts = false;
    canvasFails = false;
    bootCorrupt = false;
    connectorFetches = 0;
    configAborts = 0;
    catalogFetches = 0;
    featuredFetches = 0;
    capabilityProbes = 0;
    llmHealthFetches = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => route(input, init, configFails)),
    );
  });

  afterEach(() => {
    configHangs = false;
    llmUnhealthy = false;
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("bounds the config request so a black-holing proxy cannot freeze the shell", async () => {
    // A proxy that accepts the connection and never answers. Without a bound the
    // request stays in the air forever and the person waits on it. Boot must let
    // it go at 1,200 ms and carry on with the defaults it already has.
    configHangs = true;
    vi.useFakeTimers();
    const { result } = renderHook(() => useStudio(), { wrapper: StudioProvider });

    // Just before the bound the request is still ours to wait on.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1_199);
    });
    expect(configAborts).toBe(0);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1);
    });

    // At 1,200 ms the request was given up rather than left hanging.
    expect(configAborts).toBe(1);
    // Boot completed: the person's own work is on screen, the shell is usable, and
    // the sidecar stays unknown because config never answered.
    expect(result.current.canvas).not.toBeNull();
    expect(result.current.sidecarReachable).toBeNull();
    expect(typeof result.current.sendMessage).toBe("function");
  });

  it("paints the canvas, memory, and the shell while the sidecar has not answered", async () => {
    // A cold laptop, a sidecar still starting: the request is in the air. The
    // person's own work is on screen from local storage, not behind that answer.
    // Boot order: local data first (canvas, memory, the latest conversation),
    // the config request alongside it and never a gate, and the off-screen reads
    // last — so nothing on the first screen waits on /api/config.
    configHangs = true;
    const { result } = renderHook(() => useStudio(), { wrapper: StudioProvider });

    await waitFor(() => expect(result.current.canvas).not.toBeNull());
    await waitFor(() => expect(result.current.memory).toHaveLength(1));
    // The shell is up and usable, and the sidecar is still unknown.
    expect(typeof result.current.sendMessage).toBe("function");
    expect(result.current.settings).toBeDefined();
    expect(result.current.sidecarReachable).toBeNull();
  });

  it("answers the first message instead of refusing it", async () => {
    chatFailure = new TypeError("fetch failed");
    const { result } = renderHook(() => useStudio(), { wrapper: StudioProvider });
    await waitFor(() => expect(result.current.canvas).not.toBeNull());

    await act(async () => {
      await result.current.sendMessage("what should I work on first?");
    });

    // sendMessage settles when the send enters the queue (#410), not when the
    // turn answers, so the offline reply is awaited where it actually lands.
    await waitFor(() => {
      expect((result.current.messages.at(-1)?.content ?? "").trim().length).toBeGreaterThan(0);
    });

    const last = result.current.messages.at(-1);
    expect(last?.role).toBe("assistant");
    expect(last?.error).toBeUndefined();
    expect(last?.content.trim().length).toBeGreaterThan(0);
    // The reply says where it came from, on the reply — not in a strip above.
    expect(result.current.offlineReplyFor).toBe(last?.id);
    expect(result.current.messages.some((message) => message.role === "notice")).toBe(false);
  });

  it("calls nothing broken until the person asks", async () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => useStudio(), { wrapper: StudioProvider });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2_500);
    });

    // The idle survey ran and found nothing — and a server that was never there
    // is not an outage, so the banner bridge still has nothing to raise.
    expect(llmHealthFetches).toBeGreaterThan(0);
    expect(result.current.sidecarReachable).toBeNull();

    await act(async () => {
      await result.current.recheckConnections();
    });
    expect(result.current.sidecarReachable).toBe(false);
  });

  it("gives up the survey when the person starts talking", async () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => useStudio(), { wrapper: StudioProvider });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(500);
    });
    expect(llmHealthFetches).toBe(0);

    await act(async () => {
      await result.current.sendMessage("hello");
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000);
    });

    expect(chatAttempts).toBe(1);
    expect(llmHealthFetches).toBe(0);
  });

  it("says nothing about a model the sidecar never got to speak for", async () => {
    // A hosted studio cannot reach a sidecar, so its health probe cannot reach the
    // model either. That refusal says nothing about the model, and must not be
    // recorded as one — otherwise the amber "model offline" strip appears on a page
    // that is working exactly as designed.
    llmUnhealthy = true;
    vi.useFakeTimers();
    const { result } = renderHook(() => useStudio(), { wrapper: StudioProvider });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2_500);
    });

    expect(llmHealthFetches).toBeGreaterThan(0);
    expect(result.current.llmHealth.healthy).toBeNull();

    await act(async () => {
      await result.current.recheckConnections();
    });
    expect(result.current.llmHealth.healthy).toBe(false);
  });

  it("asks the browser for idle time, and gives it up when the person types", async () => {
    // The branch every real browser takes — jsdom has no requestIdleCallback, so the
    // timer fallback above is the one those tests exercise. The survey is scheduled for
    // idle time with a deadline, and a person who starts talking ends it.
    const requestIdle = vi.fn(() => 7);
    const cancelIdle = vi.fn();
    vi.stubGlobal("requestIdleCallback", requestIdle);
    vi.stubGlobal("cancelIdleCallback", cancelIdle);
    vi.useFakeTimers();
    const { result } = renderHook(() => useStudio(), { wrapper: StudioProvider });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1_000);
    });

    expect(requestIdle).toHaveBeenCalledWith(expect.any(Function), { timeout: 2_000 });
    expect(llmHealthFetches).toBe(0);

    await act(async () => {
      await result.current.sendMessage("hello");
    });

    expect(cancelIdle).toHaveBeenCalledWith(7);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000);
    });
    expect(llmHealthFetches).toBe(0);
  });

  it("keeps the shell usable and the off-screen reads unrequested while the browser stays busy", async () => {
    // Idle never comes: a browser under load, a background tab. The shell must
    // still be interactive — canvas, memory, and the composer — and the reads for
    // surfaces nobody opened (connectors, presets, featured, capabilities) must
    // stay unrequested until there is idle time to spend on them.
    const requestIdle = vi.fn(() => 7);
    vi.stubGlobal("requestIdleCallback", requestIdle);
    vi.stubGlobal("cancelIdleCallback", vi.fn());
    vi.useFakeTimers();
    const { result, unmount } = renderHook(() => useStudio(), { wrapper: StudioProvider });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000);
    });

    // The idle callback was asked for and never fired, so the fallback timer did
    // not run either — the deferred reads are still owed, not spent.
    expect(requestIdle).toHaveBeenCalled();
    expect(catalogFetches).toBe(0);
    expect(featuredFetches).toBe(0);
    expect(connectorFetches).toBe(0);
    expect(capabilityProbes).toBe(0);
    expect(llmHealthFetches).toBe(0);

    // Usable regardless: the person's own work is painted and the composer is live.
    expect(result.current.canvas).not.toBeNull();
    expect(result.current.memory).toHaveLength(1);
    expect(typeof result.current.sendMessage).toBe("function");

    // Unmount while the idle stub is still installed: the effect cleanup hands the
    // scheduled idle time back.
    unmount();
  });
});

describe("StudioContext on a desktop install whose model is down", () => {
  beforeEach(() => {
    llmUnhealthy = true;
    localStorage.clear();
    chatBody = null;
    chatStream = null;
    chatFailure = null;
    chatAttempts = 0;
    chatAborts = false;
    canvasFails = false;
    connectorFetches = 0;
    llmHealthFetches = 0;
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => route(input, init)));
  });

  afterEach(() => {
    llmUnhealthy = false;
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("believes the sidecar when it reports the model is not there", async () => {
    // The bar, the composer, and the offline panels all read this value. The shipped
    // desktop default is the sidecar's own proxy address, which no setting can judge —
    // so a refusal the sidecar witnessed has to be what lands. Without it a laptop with
    // Ollama switched off sits at "not checked" forever and never reaches the offline
    // path that is designed for exactly this.
    localStorage.setItem(
      "studio.settings",
      JSON.stringify({
        base_url: "http://localhost:8001/v1",
        api_key: "local",
        model_name: "local-tools-model",
        mcp_url: "http://localhost:8000/mcp",
        theme: "dark",
      }),
    );
    vi.useFakeTimers();
    const { result } = renderHook(() => useStudio(), { wrapper: StudioProvider });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2_500);
    });

    expect(result.current.sidecarReachable).toBe(true);
    expect(result.current.llmHealth.healthy).toBe(false);
    expect(result.current.llmHealth.message).toBe("connection refused");
  });
});

describe("StudioContext probe scheduling", () => {
  beforeEach(() => {
    localStorage.clear();
    chatBody = null;
    chatStream = null;
    chatFailure = null;
    chatAborts = false;
    canvasFails = false;
    bootCorrupt = false;
    connectorFetches = 0;
    llmHealthFetches = 0;
    vi.useFakeTimers();
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => route(input, init)));
  });

  afterEach(() => {
    llmUnhealthy = false;
    vi.restoreAllMocks();
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  /** Drive `document.visibilityState`, which jsdom reports as a static getter. */
  function driveVisibility(initial: DocumentVisibilityState = "visible") {
    let state = initial;
    const spy = vi
      .spyOn(document, "visibilityState", "get")
      .mockImplementation(() => state);
    return {
      hide() {
        state = "hidden";
      },
      show() {
        state = "visible";
      },
      restore() {
        spy.mockRestore();
      },
    };
  }

  it("probes on a jittered cadence while the window is visible", async () => {
    renderHook(() => useStudio(), { wrapper: StudioProvider });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2_500);
    });
    const afterBoot = llmHealthFetches;
    expect(afterBoot).toBeGreaterThan(0);

    // The scheduler armed at mount for PROBE_BASE_MS ±20%, so from mount nothing
    // fires before the shortest wait. The boot's own probe has already run.
    const shortest = PROBE_BASE_MS * (1 - PROBE_JITTER);
    const longest = PROBE_BASE_MS * (1 + PROBE_JITTER);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(shortest - 2_500 - 1_000);
    });
    expect(llmHealthFetches).toBe(afterBoot);

    // ...and one has fired by the longest.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(longest - shortest + 2_000);
    });
    expect(llmHealthFetches).toBeGreaterThan(afterBoot);
  });

  it("makes no request at all while the window is hidden", async () => {
    const visibility = driveVisibility("hidden");
    renderHook(() => useStudio(), { wrapper: StudioProvider });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2_500);
    });
    const afterBoot = llmHealthFetches;

    await act(async () => {
      await vi.advanceTimersByTimeAsync(10 * 60_000);
    });
    expect(llmHealthFetches).toBe(afterBoot);
    visibility.restore();
  });

  it("probes once when the window comes back after the answer has gone stale", async () => {
    const visibility = driveVisibility("visible");
    renderHook(() => useStudio(), { wrapper: StudioProvider });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2_500);
    });

    visibility.hide();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5 * 60_000);
    });
    const whileHidden = llmHealthFetches;

    visibility.show();
    await act(async () => {
      document.dispatchEvent(new Event("visibilitychange"));
    });
    expect(llmHealthFetches).toBe(whileHidden + 1);
    visibility.restore();
  });

  it("backs off when the model keeps refusing instead of hammering it", async () => {
    llmUnhealthy = true;
    renderHook(() => useStudio(), { wrapper: StudioProvider });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2_500);
    });
    const start = llmHealthFetches;

    await act(async () => {
      await vi.advanceTimersByTimeAsync(10 * 60_000);
    });
    const refused = llmHealthFetches - start;
    // Ten minutes at the base cadence is about twenty probes; the ladder asks
    // fewer than a third of that, and jitter cannot move a count across that gap.
    expect(refused).toBeGreaterThan(0);
    expect(refused).toBeLessThan(8);
  });

  it("collapses a burst of endpoint edits into one debounced probe", async () => {
    const { result } = renderHook(() => useStudio(), { wrapper: StudioProvider });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2_500);
    });
    const before = llmHealthFetches;

    act(() => {
      result.current.saveSettings({ ...result.current.settings, base_url: "http://localhost:8001/v1" });
      result.current.saveSettings({ ...result.current.settings, base_url: "http://localhost:8002/v1" });
      result.current.saveSettings({ ...result.current.settings, base_url: "http://localhost:8003/v1" });
    });
    // Typing a URL is many saves in a row; none of them probes yet.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(PROBE_SETTINGS_DEBOUNCE_MS - 1);
    });
    expect(llmHealthFetches).toBe(before);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1);
    });
    expect(llmHealthFetches).toBe(before + 1);
  });

  it("does not probe when an edit leaves the endpoints alone", async () => {
    const { result } = renderHook(() => useStudio(), { wrapper: StudioProvider });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2_500);
    });
    const before = llmHealthFetches;

    act(() => {
      result.current.saveSettings({ ...result.current.settings, theme: "light" });
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(PROBE_SETTINGS_DEBOUNCE_MS + 1_000);
    });
    expect(llmHealthFetches).toBe(before);
  });
});

describe("StudioContext signal inbox", () => {
  beforeEach(() => {
    localStorage.clear();
    signalFetches = 0;
    vi.useFakeTimers();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => route(input, init)),
    );
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("loads the inbox on boot and keeps polling while the window is visible", async () => {
    const { result } = renderHook(() => useStudio(), { wrapper: StudioProvider });
    await act(async () => {
      await Promise.resolve();
    });
    expect(signalFetches).toBeGreaterThan(0);
    expect(result.current.signals).toEqual([]);
    expect(result.current.signalsError).toBeNull();

    const afterBoot = signalFetches;
    await act(async () => {
      vi.advanceTimersByTime(60_000);
    });
    expect(signalFetches).toBeGreaterThan(afterBoot);

    const afterInterval = signalFetches;
    await act(async () => {
      document.dispatchEvent(new Event("visibilitychange"));
    });
    expect(signalFetches).toBeGreaterThan(afterInterval);
  });
});

describe("StudioContext theme", () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.className = "";
    chatBody = null;
    chatStream = null;
    chatFailure = null;
    chatAborts = false;
    canvasFails = false;
    bootCorrupt = false;
    connectorFetches = 0;
    llmHealthFetches = 0;
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => route(input, init)));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    document.documentElement.className = "";
  });

  it("applies the stored theme and persists a change", async () => {
    const { result } = renderHook(() => useStudio(), { wrapper: StudioProvider });
    await waitFor(() => expect(result.current.conversationId).toBe("c-1"));

    expect(document.documentElement.classList.contains("theme-dark")).toBe(true);

    act(() => {
      result.current.saveSettings({ ...result.current.settings, theme: "light" });
    });

    expect(document.documentElement.classList.contains("theme-light")).toBe(true);
    expect(JSON.parse(localStorage.getItem("studio.settings") ?? "{}").theme).toBe("light");
  });

  it("keeps the chosen theme across a remount", async () => {
    localStorage.setItem("studio.settings", JSON.stringify({ theme: "light" }));
    const { unmount } = renderHook(() => useStudio(), { wrapper: StudioProvider });
    await waitFor(() => expect(document.documentElement.classList.contains("theme-light")).toBe(true));

    unmount();
    document.documentElement.className = "";

    const second = renderHook(() => useStudio(), { wrapper: StudioProvider });
    await waitFor(() => expect(second.result.current.settings.theme).toBe("light"));
    expect(document.documentElement.classList.contains("theme-light")).toBe(true);
  });
});

describe("StudioContext canvas state", () => {
  beforeEach(() => {
    localStorage.clear();
    chatBody = null;
    chatStream = null;
    chatFailure = null;
    chatAborts = false;
    canvasFails = false;
    bootCorrupt = false;
    connectorFetches = 0;
    llmHealthFetches = 0;
    approvalCalls = [];
    headPatches = [];
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

describe("StudioContext stopped turns", () => {
  beforeEach(() => {
    localStorage.clear();
    chatBody = null;
    chatStream = null;
    chatFailure = null;
    chatAborts = false;
    canvasFails = false;
    bootCorrupt = false;
    connectorFetches = 0;
    llmHealthFetches = 0;
    approvalCalls = [];
    headPatches = [];
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => route(input, init)));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("keeps the question but shows no failure when the user stops the turn", async () => {
    chatAborts = true;
    const { result } = renderHook(() => useStudio(), { wrapper: StudioProvider });
    await waitFor(() => expect(result.current.conversationId).toBe("c-1"));

    await act(async () => {
      await result.current.sendMessage("list the jobs");
    });

    const messages = result.current.messages;
    expect(messages.some((message) => message.role === "user" && message.content === "list the jobs")).toBe(true);
    expect(messages.at(-1)?.error).toBeUndefined();
  });
});

describe("StudioContext write approval and branches", () => {
  beforeEach(() => {
    localStorage.clear();
    chatBody = null;
    chatStream = null;
    chatFailure = null;
    chatAborts = false;
    canvasFails = false;
    bootCorrupt = false;
    connectorFetches = 0;
    llmHealthFetches = 0;
    approvalCalls = [];
    headPatches = [];
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => route(input, init)));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("holds a write as a question until the person answers it", async () => {
    chatStream =
      'event: approval\ndata: {"id":"apv_1","tool_call_id":"call-1","name":"add_job","prompt":"Allow the assistant to add job?"}\n\n' +
      'event: message\ndata: {"content":"Added."}\n\n';

    const { result } = renderHook(() => useStudio(), { wrapper: StudioProvider });
    await waitFor(() => expect(result.current.conversationId).toBe("c-1"));

    await act(async () => {
      await result.current.sendMessage("add a job for Retention");
    });

    const part = result.current.messages
      .flatMap((message) => message.parts ?? [])
      .find((candidate) => candidate.kind === "tool" && candidate.name === "add_job");
    expect(part).toBeDefined();

    await act(async () => {
      await result.current.respondToApproval("apv_1", true, "yes please");
    });

    expect(approvalCalls).toEqual([{ approved: true, reason: "yes please" }]);
  });

  it("asks the server for approval before any write", async () => {
    const { result } = renderHook(() => useStudio(), { wrapper: StudioProvider });
    await waitFor(() => expect(result.current.conversationId).toBe("c-1"));

    await act(async () => {
      await result.current.sendMessage("hello");
    });

    expect(chatBody).toMatchObject({ approvals: true });
    expect(typeof chatBody?.assistant_id).toBe("string");
  });

  it("persists the branch a person switched to", async () => {
    const { result } = renderHook(() => useStudio(), { wrapper: StudioProvider });
    await waitFor(() => expect(result.current.conversationId).toBe("c-1"));

    await act(async () => {
      result.current.switchBranch([
        { id: "b-1", parentId: null, role: "user", content: "first" },
        { id: "b-2", parentId: "b-1", role: "assistant", content: "answer" },
      ]);
    });

    expect(result.current.messages.map((message) => message.id)).toEqual(["b-1", "b-2"]);
    await waitFor(() => expect(headPatches).toEqual([{ head_id: "b-2" }]));
  });
});

describe("StudioContext boot failure", () => {
  beforeEach(() => {
    bootCorrupt = true;
    localStorage.clear();
    chatBody = null;
    chatStream = null;
    chatFailure = null;
    chatAttempts = 0;
    chatAborts = false;
    canvasFails = false;
    connectorFetches = 0;
    llmHealthFetches = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => route(input, init)),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("surfaces a store-corrupt failure as bootError, not as a down sidecar", async () => {
    const { result } = renderHook(() => useStudio(), { wrapper: StudioProvider });

    await waitFor(() => expect(result.current.bootError).not.toBeNull());

    expect(result.current.bootError?.code).toBe("store_corrupt");
    expect(result.current.bootError?.message).toContain("/home/me/.odi.db");
    // The sidecar answered, so it is reachable; the database is the problem.
    expect(result.current.sidecarReachable).toBe(true);
  });

  it("clears the failure page once a restored store answers cleanly", async () => {
    const { result } = renderHook(() => useStudio(), { wrapper: StudioProvider });

    await waitFor(() => expect(result.current.bootError).not.toBeNull());

    // The person restored a backup; the next probe answers cleanly.
    bootCorrupt = false;
    await act(async () => {
      await result.current.recheckBoot();
    });

    expect(result.current.bootError).toBeNull();
    expect(result.current.sidecarReachable).toBe(true);
  });
});

describe("StudioContext startNewThread (#319)", () => {
  // A turn that leaves a tool call, an offline flag, and its own conversation
  // id behind — everything the Undo snapshot has to carry back.
  const RICH_STREAM =
    'event: conversation\ndata: {"id":"c-9","title":"thread"}\n\n' +
    'event: status\ndata: {"phase":"offline"}\n\n' +
    'event: tool\ndata: {"name":"list_jobs","status":"ok","preview":"3 jobs"}\n\n' +
    'event: delta\ndata: {"text":"Three jobs."}\n\n' +
    'event: message\ndata: {"content":"Three jobs."}\n\n';

  beforeEach(() => {
    localStorage.clear();
    chatBody = null;
    chatStream = RICH_STREAM;
    chatFailure = null;
    chatAttempts = 0;
    chatAborts = false;
    chatHangs = false;
    releaseChat = null;
    canvasFails = false;
    bootCorrupt = false;
    connectorFetches = 0;
    llmHealthFetches = 0;
    approvalCalls = [];
    headPatches = [];
    conversationCreates = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => route(input, init)),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    chatStream = null;
    chatHangs = false;
    releaseChat = null;
    document.body.innerHTML = "";
  });

  async function booted() {
    const harness = renderHook(() => useStudio(), { wrapper: StudioProvider });
    await waitFor(() => expect(harness.result.current.conversationId).toBe("c-1"));
    return harness;
  }

  async function threadWithOneTurn() {
    const harness = await booted();
    await act(async () => {
      await harness.result.current.sendMessage("How many jobs?");
    });
    expect(harness.result.current.messages.length).toBeGreaterThan(1);
    expect(harness.result.current.conversationId).toBe("c-9");
    return harness;
  }

  it("refuses to start a new thread while a reply is still coming", async () => {
    const harness = await booted();
    chatHangs = true;
    await act(async () => {
      void harness.result.current.sendMessage("How many jobs?");
    });
    expect(harness.result.current.streaming).toBe(true);
    const before = harness.result.current.messages;

    const handle = harness.result.current.startNewThread();

    expect(handle).toBeNull();
    expect(harness.result.current.messages).toEqual(before);
    expect(harness.result.current.streaming).toBe(true);

    await act(async () => {
      releaseChat?.();
    });
  });

  it("aborts the reply when told to stop it", async () => {
    const harness = await booted();
    chatHangs = true;
    await act(async () => {
      void harness.result.current.sendMessage("How many jobs?");
    });

    await act(async () => {
      harness.result.current.startNewThread({ stop: true });
      releaseChat?.();
    });

    expect(harness.result.current.streaming).toBe(false);
    expect(harness.result.current.messages).toEqual([]);
  });

  it("creates no conversation until the first message", async () => {
    const harness = await threadWithOneTurn();
    expect(conversationCreates).toBe(0);

    await act(async () => {
      harness.result.current.startNewThread();
    });

    expect(conversationCreates).toBe(0);
    expect(harness.result.current.conversationId).toBeNull();
    expect(harness.result.current.messages).toEqual([]);

    chatStream = null;
    await act(async () => {
      await harness.result.current.sendMessage("A new question.");
    });

    expect(harness.result.current.conversationId).toBe("c-2");
    expect(chatBody?.conversation_id).toBeNull();
  });

  it("restores the thread exactly when Undo runs inside the ten seconds", async () => {
    const viewport = document.createElement("div");
    viewport.className = "chat__scroll";
    Object.defineProperty(viewport, "scrollTop", {
      configurable: true,
      writable: true,
      value: 812,
    });
    document.body.append(viewport);

    const harness = await threadWithOneTurn();
    const before = harness.result.current.messages;
    const beforeToolActivity = harness.result.current.toolActivity;
    const beforeOfflineReply = harness.result.current.offlineReplyFor;
    // The undo has to bring something back, not compare two empties.
    expect(beforeToolActivity.length).toBeGreaterThan(0);

    let handle!: ReturnType<typeof harness.result.current.startNewThread>;
    await act(async () => {
      handle = harness.result.current.startNewThread();
    });
    expect(handle).not.toBeNull();

    viewport.scrollTop = 0;
    await act(async () => {
      handle?.undo();
    });

    expect(harness.result.current.messages).toEqual(before);
    expect(harness.result.current.messages.map((message) => message.id)).toEqual(
      before.map((message) => message.id),
    );
    expect(harness.result.current.messages.map((message) => message.parentId)).toEqual(
      before.map((message) => message.parentId),
    );
    expect(harness.result.current.conversationId).toBe("c-9");
    expect(harness.result.current.toolActivity).toEqual(beforeToolActivity);
    expect(harness.result.current.offlineReplyFor).toBe(beforeOfflineReply);
    expect(viewport.scrollTop).toBe(812);
  });

  it("offers a ten-second Undo and stops offering it once a message is sent", async () => {
    const harness = await threadWithOneTurn();

    let handle!: ReturnType<typeof harness.result.current.startNewThread>;
    await act(async () => {
      handle = harness.result.current.startNewThread();
    });

    const undoToast = harness.result.current.toasts.at(-1);
    expect(undoToast?.message).toBe("New thread. Your last one is still saved.");
    expect(undoToast?.action?.label).toBe("Undo");
    expect(undoToast?.durationMs).toBe(10_000);

    chatStream = null;
    await act(async () => {
      await harness.result.current.sendMessage("A new question.");
    });

    expect(harness.result.current.toasts.some((toast) => toast.action?.label === "Undo")).toBe(false);
    expect(harness.result.current.toasts.at(-1)?.message).toBe("New thread started.");

    const messagesAfter = harness.result.current.messages;
    await act(async () => {
      handle?.undo();
    });
    expect(harness.result.current.messages).toBe(messagesAfter);
    expect(harness.result.current.conversationId).toBe("c-2");
  });

  it("leaves the canvas, brief, memory, and connectors where they were", async () => {
    const harness = await threadWithOneTurn();
    await waitFor(() => expect(harness.result.current.connectors.length).toBeGreaterThanOrEqual(0));
    const before = JSON.stringify({
      canvas: harness.result.current.canvas,
      brief: harness.result.current.brief,
      memory: harness.result.current.memory,
      connectors: harness.result.current.connectors,
      settings: harness.result.current.settings,
    });

    await act(async () => {
      harness.result.current.startNewThread();
    });

    const after = JSON.stringify({
      canvas: harness.result.current.canvas,
      brief: harness.result.current.brief,
      memory: harness.result.current.memory,
      connectors: harness.result.current.connectors,
      settings: harness.result.current.settings,
    });
    expect(after).toBe(before);
  });
});

describe("StudioContext follow-up queue (#410)", () => {
  beforeEach(() => {
    localStorage.clear();
    chatBody = null;
    chatAttempts = 0;
    chatStream = null;
    chatFailure = null;
    chatAborts = false;
    canvasFails = false;
    gateChats = true;
    gatedTurns = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => route(input, init)),
    );
  });

  afterEach(() => {
    gateChats = false;
    vi.unstubAllGlobals();
  });

  async function openStudio() {
    const { result } = renderHook(() => useStudio(), { wrapper: StudioProvider });
    await waitFor(() => expect(result.current.conversationId).toBe("c-1"));
    await waitFor(() => expect(result.current.queue).not.toBeNull());
    return result;
  }

  /** The question the sidecar was actually asked on one gated turn. */
  function turnText(turn: GatedTurn): string {
    const history = (turn.body.messages ?? []) as { content: string }[];
    return history[history.length - 1]?.content ?? "";
  }

  function laneTexts(items: readonly { parts: readonly { type: string; text?: string }[] }[]): string[] {
    return items.map((item) =>
      item.parts.flatMap((part) => (part.type === "text" ? [part.text ?? ""] : [])).join(" "),
    );
  }

  // The adapter mounts on the first effect, so it is present once openStudio
  // resolves; this narrows the nullable context field for the assertions below.
  type StudioResult = Awaited<ReturnType<typeof openStudio>>;
  function lane(
    result: StudioResult,
  ): NonNullable<StudioResult["current"]["queue"]> {
    const queue = result.current.queue;
    if (!queue) {
      throw new Error("queue adapter missing");
    }
    return queue;
  }

  it("holds follow-ups typed during an answer and sends them in order", async () => {
    const result = await openStudio();

    await act(async () => {
      await result.current.sendMessage("first question?");
    });
    await waitFor(() => expect(gatedTurns).toHaveLength(1));
    expect(result.current.streaming).toBe(true);

    await act(async () => {
      await result.current.sendMessage("second question?");
      await result.current.sendMessage("third question?");
    });

    // Never two streams for one conversation: the follow-ups wait in the lane.
    expect(gatedTurns).toHaveLength(1);
    expect(laneTexts(lane(result).items)).toEqual([
      "second question?",
      "third question?",
    ]);

    await act(async () => {
      gatedTurns[0].respond(DEFAULT_CHAT_STREAM);
    });
    await waitFor(() => expect(gatedTurns).toHaveLength(2));
    await act(async () => {
      gatedTurns[1].respond(DEFAULT_CHAT_STREAM);
    });
    await waitFor(() => expect(gatedTurns).toHaveLength(3));
    await act(async () => {
      gatedTurns[2].respond(DEFAULT_CHAT_STREAM);
    });
    await waitFor(() => expect(result.current.streaming).toBe(false));

    expect(gatedTurns.map(turnText)).toEqual([
      "first question?",
      "second question?",
      "third question?",
    ]);
  });

  it("a steered follow-up cuts in, cancelling the live answer exactly once", async () => {
    const result = await openStudio();

    await act(async () => {
      await result.current.sendMessage("long question?");
    });
    await waitFor(() => expect(gatedTurns).toHaveLength(1));

    await act(async () => {
      lane(result).steer(queuedUserMessage("urgent correction"));
    });

    // The live stream aborts and the steer is dispatched at once — a cut-in,
    // not a second stream: exactly one new request was made.
    await waitFor(() => expect(gatedTurns).toHaveLength(2));
    await waitFor(() => expect(gatedTurns[0].aborted).toBe(true));
    expect(gatedTurns[1].aborted).toBe(false);
    expect(chatAttempts).toBe(2);

    await act(async () => {
      gatedTurns[1].respond(DEFAULT_CHAT_STREAM);
    });
    await waitFor(() => expect(result.current.streaming).toBe(false));
    expect(turnText(gatedTurns[1])).toBe("urgent correction");
    // The interrupted question stays in the transcript; only its empty
    // answer is dropped.
    expect(result.current.messages.some((message) => message.content === "long question?")).toBe(true);
  });

  it("a follow-up removed from the lane is never fetched", async () => {
    const result = await openStudio();

    await act(async () => {
      await result.current.sendMessage("running question?");
    });
    await waitFor(() => expect(gatedTurns).toHaveLength(1));
    await act(async () => {
      await result.current.sendMessage("withdrawn question?");
    });
    const [item] = lane(result).items;
    await act(async () => {
      lane(result).remove(item.id);
    });
    expect(lane(result).items).toHaveLength(0);

    await act(async () => {
      gatedTurns[0].respond(DEFAULT_CHAT_STREAM);
    });
    await waitFor(() => expect(result.current.streaming).toBe(false));
    expect(gatedTurns).toHaveLength(1);
    expect(
      result.current.messages.some((message) => message.content === "withdrawn question?"),
    ).toBe(false);
  });

  it("stopping the answer keeps the lane waiting for the next send", async () => {
    const result = await openStudio();

    await act(async () => {
      await result.current.sendMessage("first?");
    });
    await waitFor(() => expect(gatedTurns).toHaveLength(1));
    await act(async () => {
      await result.current.sendMessage("second?");
    });

    await act(async () => {
      result.current.stopStreaming();
    });
    await waitFor(() => expect(result.current.streaming).toBe(false));
    // Stop takes down the turn, not the person's follow-ups (#410): the lane
    // keeps "second?" and waits — nothing fires off behind the stop.
    expect(gatedTurns).toHaveLength(1);
    expect(laneTexts(lane(result).items)).toEqual(["second?"]);

    await act(async () => {
      await result.current.sendMessage("third?");
    });
    // The next send re-arms the lane, and the older follow-up answers first.
    await waitFor(() => expect(gatedTurns).toHaveLength(2));
    expect(turnText(gatedTurns[1])).toBe("second?");
    await act(async () => {
      gatedTurns[1].respond(DEFAULT_CHAT_STREAM);
    });
    await waitFor(() => expect(gatedTurns).toHaveLength(3));
    expect(turnText(gatedTurns[2])).toBe("third?");
    await act(async () => {
      gatedTurns[2].respond(DEFAULT_CHAT_STREAM);
    });
    await waitFor(() => expect(result.current.streaming).toBe(false));
  });
});

describe("StudioContext agent focus", () => {
  beforeEach(() => {
    localStorage.clear();
    chatBody = null;
    chatStream = null;
    chatFailure = null;
    chatAttempts = 0;
    bootCorrupt = false;
    chatAborts = false;
    canvasFails = false;
    canvasRecords = {};
    connectorFetches = 0;
    llmHealthFetches = 0;
    approvalCalls = [];
    headPatches = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => route(input, init)),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("sends the selected record as a pointer the sidecar can verify", async () => {
    const { result } = renderHook(() => useStudio(), { wrapper: StudioProvider });
    await waitFor(() => expect(result.current.conversationId).toBe("c-1"));

    act(() => {
      result.current.focusSubject("outcome", "O-9");
    });
    await act(async () => {
      await result.current.sendMessage("what would have to be true?");
    });

    expect(chatBody?.focus).toEqual({ kind: "outcome", id: "O-9" });
  });

  it("sends no focus when the screen has nothing selected", async () => {
    const { result } = renderHook(() => useStudio(), { wrapper: StudioProvider });
    await waitFor(() => expect(result.current.conversationId).toBe("c-1"));

    await act(async () => {
      await result.current.sendMessage("what would have to be true?");
    });

    expect(chatBody?.focus ?? null).toBeNull();
  });

  it("does not point at a record the sidecar cannot read", async () => {
    const { result } = renderHook(() => useStudio(), { wrapper: StudioProvider });
    await waitFor(() => expect(result.current.conversationId).toBe("c-1"));

    act(() => {
      result.current.focusSubject("strategy", "S-1");
    });
    await act(async () => {
      await result.current.sendMessage("what would have to be true?");
    });

    expect(chatBody?.focus ?? null).toBeNull();
  });

  it("stops pointing at the screen once the person clears the focus", async () => {
    const { result } = renderHook(() => useStudio(), { wrapper: StudioProvider });
    await waitFor(() => expect(result.current.conversationId).toBe("c-1"));

    act(() => {
      result.current.focusSubject("outcome", "O-9");
    });
    expect(result.current.focusedSubject).toEqual({ kind: "outcome", id: "O-9" });
    // Focusing a record is remembered for the next visit, so clearing must undo it.
    expect(localStorage.getItem("studio.session")).toContain("O-9");

    act(() => {
      result.current.clearFocus();
    });

    expect(result.current.focusedSubject).toBeNull();
    expect(localStorage.getItem("studio.session")).toBeNull();

    await act(async () => {
      await result.current.sendMessage("what would have to be true?");
    });

    expect(chatBody?.focus ?? null).toBeNull();
  });

  it("names the focused record with the words the snapshot holds", async () => {
    canvasRecords = {
      outcomes: [{ id: "O-9", statement: "Reduce the time to reconcile a failed payment" }],
    };
    const { result } = renderHook(() => useStudio(), { wrapper: StudioProvider });
    await waitFor(() => expect(result.current.conversationId).toBe("c-1"));

    act(() => {
      result.current.focusSubject("outcome", "O-9");
    });

    await waitFor(() =>
      expect(result.current.focusedSubjectLabel).toBe(
        "Reduce the time to reconcile a failed payment",
      ),
    );
  });

  it("names nothing for a selection this snapshot does not hold", async () => {
    canvasRecords = {
      outcomes: [{ id: "O-9", statement: "An outcome that is still on the board" }],
    };
    const { result } = renderHook(() => useStudio(), { wrapper: StudioProvider });
    await waitFor(() => expect(result.current.conversationId).toBe("c-1"));

    act(() => {
      result.current.focusSubject("outcome", "deleted-yesterday");
    });

    // The pointer still travels — the sidecar answers nothing it cannot read —
    // but the composer has no words to claim, so no chip may appear.
    expect(result.current.focusedSubject).toEqual({ kind: "outcome", id: "deleted-yesterday" });
    expect(result.current.focusedSubjectLabel).toBeNull();
  });
});

describe("Studio render budget (#502)", () => {
  // The boot fires a health probe, a canvas read, and a connector list, and
  // their answers land whenever the microtask queue feels like it. A scenario
  // that started before they did would be counting that race, not the
  // interaction, so the stub below tracks how many calls are still open.
  let inFlight = 0;

  beforeEach(() => {
    localStorage.clear();
    chatBody = null;
    chatStream = null;
    chatFailure = null;
    chatAborts = false;
    canvasFails = false;
    canvasRecords = {};
    bootCorrupt = false;
    llmUnhealthy = false;
    inFlight = 0;
    resetCounts();
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      inFlight += 1;
      try {
        return await route(input, init);
      } finally {
        inFlight -= 1;
      }
    }));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  async function countedStudio(): Promise<StudioContextValue> {
    let studio: StudioContextValue | null = null;
    render(<CountedStudio onStudio={(value) => { studio = value; }} />);
    await waitFor(() => expect(studio).not.toBeNull());
    // Let the boot's own answers arrive and commit before the count starts: a
    // budget measures one interaction, and nothing else.
    await act(async () => {
      for (let tick = 0; tick < 10; tick += 1) {
        await new Promise((settleTick) => { setTimeout(settleTick, 0); });
      }
    });
    expect(inFlight, "the boot never went quiet").toBe(0);
    resetCounts();
    return studio as unknown as StudioContextValue;
  }

  it("counts each of the four pinned surfaces while a reply streams", async () => {
    chatStream = streamOfDeltas(40);
    const studio = await countedStudio();

    await act(async () => {
      await studio.sendMessage("hello");
    });

    expect(Object.keys(getCounts()).sort()).toEqual([
      "banners",
      "composer",
      "landscape",
      "rail",
    ]);
  });

  // Baseline measured on 2026-11-05 at commit c403ba17: the commits each pinned
  // surface makes for one interaction, counted from a boot that has gone quiet.
  // Exact on purpose — the state splits (#503, #504, #505) may only lower a
  // number here, and a rise has to be argued with, surface by surface.
  //
  // What they say: a keystroke renders the composer twice and nothing else; a
  // streamed reply renders the composer five times and the rest of the screen
  // twice; one health flip reaches every surface, and turns a single boolean
  // into five renders of the banner area.
  const STREAM_BUDGET = { banners: 2, composer: 5, landscape: 2, rail: 2 };
  const TYPING_BUDGET = { banners: 0, composer: 40, landscape: 0, rail: 0 };
  const HEALTH_BUDGET = { banners: 5, composer: 1, landscape: 1, rail: 1 };

  it("streams forty deltas within its budget", async () => {
    chatStream = streamOfDeltas(40);
    const studio = await countedStudio();

    await act(async () => {
      await studio.sendMessage("hello");
    });

    expectRenderBudget(STREAM_BUDGET);
  });

  it("takes twenty keystrokes within its budget", async () => {
    await countedStudio();
    const input = screen.getByRole("textbox", { name: "Message the studio" });

    await act(async () => {
      typeIntoComposer(input as HTMLTextAreaElement, 20);
    });

    expectRenderBudget(TYPING_BUDGET);
  });

  it("answers one health poll turning unhealthy within its budget", async () => {
    await countedStudio();
    llmUnhealthy = true;

    await act(async () => {
      document.dispatchEvent(new Event("visibilitychange"));
    });

    expectRenderBudget(HEALTH_BUDGET);
  });
});
