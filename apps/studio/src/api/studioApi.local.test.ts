import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  StudioApiError,
  fetchCanvas,
  fetchConversationTree,
  fetchMemory,
  isTransportFailure,
  listConversations,
  streamChat,
} from "./studioApi";

const bff = {
  data: { fetchCanvas: vi.fn() },
  memory: {
    listObservations: vi.fn(),
    listConversations: vi.fn(),
    getConversation: vi.fn(),
    conversationTree: vi.fn(),
  },
  chat: { stream: vi.fn() },
};

vi.mock("../bff/index", () => ({
  getStudioBff: vi.fn(() => Promise.resolve(bff)),
}));

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(async () => jsonResponse({})));
  vi.mocked(bff.data.fetchCanvas).mockReset();
  vi.mocked(bff.memory.listObservations).mockReset();
  vi.mocked(bff.memory.listConversations).mockReset();
  vi.mocked(bff.memory.getConversation).mockReset();
  vi.mocked(bff.memory.conversationTree).mockReset();
  vi.mocked(bff.chat.stream).mockReset();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("isTransportFailure", () => {
  it("treats 502 without a sidecar error body as transport", () => {
    expect(
      isTransportFailure(new StudioApiError({ code: "internal", message: "down", retryable: false }, 502, false)),
    ).toBe(true);
  });

  it("treats a sidecar 502 with a structured error as not transport", () => {
    expect(
      isTransportFailure(new StudioApiError({ code: "mcp_unreachable", message: "down", retryable: true }, 502, true)),
    ).toBe(false);
  });

  it("treats network errors as transport", () => {
    expect(isTransportFailure(new TypeError("failed to fetch"))).toBe(true);
  });
});

describe("fetchCanvas fallback", () => {
  it("falls back to the local BFF when the sidecar returns 502 with a proxy detail", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse({ detail: "Sidecar unreachable" }, 502));
    vi.mocked(bff.data.fetchCanvas).mockResolvedValueOnce({ jobs: [], steps: [], outcomes: [], source: "local" });

    const canvas = await fetchCanvas("http://mcp");
    expect(canvas.source).toBe("local");
    expect(bff.data.fetchCanvas).toHaveBeenCalled();
  });

  it("does not fall back for a sidecar 502 with a structured error", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse({ error: { code: "mcp_unreachable", message: "down", retryable: true } }, 502));
    await expect(fetchCanvas("http://mcp")).rejects.toThrow();
    expect(bff.data.fetchCanvas).not.toHaveBeenCalled();
  });

  it("does not fall back for a sidecar 422", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse({ error: { code: "validation", message: "bad" } }, 422));
    await expect(fetchCanvas("http://mcp")).rejects.toThrow();
    expect(bff.data.fetchCanvas).not.toHaveBeenCalled();
  });
});

describe("fetchMemory fallback", () => {
  it("falls back to the local BFF when the sidecar returns 502", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse({ detail: "Sidecar unreachable" }, 502));
    vi.mocked(bff.memory.listObservations).mockResolvedValueOnce([]);

    await fetchMemory();
    expect(bff.memory.listObservations).toHaveBeenCalled();
  });
});

describe("streamChat fallback", () => {
  it("falls back to the local BFF when the sidecar returns 502", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse({ detail: "SIDECAR_URL is not configured" }, 502));
    vi.mocked(bff.chat.stream).mockResolvedValueOnce(undefined);

    await streamChat(
      { base_url: "", api_key: "", model: "", mcp_url: "", messages: [] },
      () => {},
    );
    expect(bff.chat.stream).toHaveBeenCalled();
  });

  it("does not fall back for a sidecar 500", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse({ error: { code: "internal", message: "boom" } }, 500));
    await expect(
      streamChat({ base_url: "", api_key: "", model: "", mcp_url: "", messages: [] }, () => {}),
    ).rejects.toThrow();
    expect(bff.chat.stream).not.toHaveBeenCalled();
  });
});

describe("listConversations fallback", () => {
  it("falls back to the local BFF when the sidecar returns 502", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse({ detail: "Sidecar unreachable" }, 502));
    vi.mocked(bff.memory.listConversations).mockResolvedValueOnce([
      {
        id: "c-1",
        title: "Activation model",
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-02T00:00:00Z",
        head_id: "m-2",
        turn_count: 2,
      },
    ]);

    const listed = await listConversations();

    expect(listed.map((item) => [item.id, item.turn_count])).toEqual([["c-1", 2]]);
    expect(bff.memory.listConversations).toHaveBeenCalled();
  });

  it("serves the sidecar list while the sidecar answers", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      jsonResponse({ conversations: [{ id: "c-2", title: "", created_at: "x", updated_at: "x", head_id: null, turn_count: 0 }] }),
    );

    const listed = await listConversations();

    expect(listed.map((item) => item.id)).toEqual(["c-2"]);
    expect(bff.memory.listConversations).not.toHaveBeenCalled();
  });
});

function serverTree(headId: string, ids: string[]) {
  const conversation = {
    id: "c-1",
    title: "Activation model",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    head_id: headId,
  };
  return jsonResponse({
    conversation,
    messages: ids.map((id) => ({
      id,
      parent_id: null,
      role: "user",
      content: `asked as ${id}`,
      created_at: "2026-01-01T09:00:00Z",
    })),
    head_id: headId,
  });
}

/** What this browser recorded for the same conversation id. */
function localTurns() {
  return [
    {
      id: 7,
      conversation_id: "c-1",
      role: "user",
      content: "Where do I start?",
      created_at: "2026-01-02T09:00:00Z",
      message_id: "q-2",
      parent_id: "m-1",
    },
    {
      id: 8,
      conversation_id: "c-1",
      role: "assistant",
      content: "Start with the job, then the outcome.",
      created_at: "2026-01-02T09:00:05Z",
      message_id: "a-2",
      parent_id: "q-2",
      provenance: "edge",
    },
  ];
}

describe("fetchConversationTree with the browser's own turns", () => {
  it("shows what this browser answered next to the server's thread", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(serverTree("m-1", ["m-1"]));
    vi.mocked(bff.memory.getConversation).mockResolvedValueOnce({ id: "c-1" });
    vi.mocked(bff.memory.conversationTree).mockResolvedValueOnce({
      conversation: { id: "c-1" },
      messages: localTurns(),
      head_id: "a-2",
    });

    const tree = await fetchConversationTree("c-1");

    expect(tree.messages.map((turn) => turn.id)).toEqual(["m-1", "q-2", "a-2"]);
    expect(tree.messages[2]?.provenance).toBe("edge");
  });

  it("reopens on the last turn answered, whoever answered it", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(serverTree("m-1", ["m-1"]));
    vi.mocked(bff.memory.getConversation).mockResolvedValueOnce({ id: "c-1" });
    vi.mocked(bff.memory.conversationTree).mockResolvedValueOnce({
      conversation: { id: "c-1" },
      messages: localTurns(),
      head_id: "a-2",
    });

    const tree = await fetchConversationTree("c-1");

    expect(tree.head_id).toBe("a-2");
  });

  it("names the browser as the brain when only the browser holds the thread", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse({ detail: "Sidecar unreachable" }, 502));
    vi.mocked(bff.memory.conversationTree).mockResolvedValueOnce({
      conversation: { id: "c-1" },
      messages: localTurns(),
      head_id: "a-2",
    });
    vi.mocked(bff.memory.getConversation).mockResolvedValueOnce({ id: "c-1" });

    const tree = await fetchConversationTree("c-1");

    expect(tree.messages.map((turn) => turn.id)).toEqual(["q-2", "a-2"]);
    expect(tree.messages[1]?.provenance).toBe("edge");
  });

  it("keeps the branch that was left open when the browser's turns are older", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      jsonResponse({
        conversation: { id: "c-1", title: "", created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z", head_id: "m-1" },
        messages: [
          { id: "m-1", parent_id: null, role: "user", content: "left here", created_at: "2026-01-01T09:00:00Z" },
          { id: "m-2", parent_id: null, role: "user", content: "the other branch", created_at: "2026-01-01T10:00:00Z" },
        ],
        head_id: "m-1",
      }),
    );
    vi.mocked(bff.memory.getConversation).mockResolvedValueOnce({ id: "c-1" });
    vi.mocked(bff.memory.conversationTree).mockResolvedValueOnce({
      conversation: { id: "c-1" },
      messages: [
        { id: 7, conversation_id: "c-1", role: "assistant", content: "answered first", created_at: "2026-01-01T08:00:00Z", message_id: "a-0", parent_id: null },
      ],
      head_id: "a-0",
    });

    const tree = await fetchConversationTree("c-1");

    expect(tree.messages.map((turn) => turn.id)).toEqual(["m-1", "m-2", "a-0"]);
    expect(tree.head_id).toBe("m-1");
  });

  it("keeps the server's thread when this browser holds none", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(serverTree("m-1", ["m-1"]));
    vi.mocked(bff.memory.getConversation).mockResolvedValueOnce(undefined);

    const tree = await fetchConversationTree("c-1");

    expect(tree.messages.map((turn) => turn.id)).toEqual(["m-1"]);
    expect(tree.head_id).toBe("m-1");
  });

  it("keeps the server's thread when the browser's own memory will not open", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(serverTree("m-1", ["m-1"]));
    vi.mocked(bff.memory.getConversation).mockRejectedValueOnce(new Error("IndexedDB blocked"));

    const tree = await fetchConversationTree("c-1");

    expect(tree.messages.map((turn) => turn.id)).toEqual(["m-1"]);
    expect(tree.head_id).toBe("m-1");
  });
});
