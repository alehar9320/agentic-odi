import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { StudioApiError, fetchCanvas, fetchMemory, isTransportFailure, listConversations, renameConversation, streamChat } from "./studioApi";

const bff = {
  data: { fetchCanvas: vi.fn() },
  memory: { listObservations: vi.fn(), listConversations: vi.fn(), renameConversation: vi.fn() },
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
  vi.mocked(bff.memory.renameConversation).mockReset();
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

describe("renameConversation", () => {
  it("patches the trimmed title through the sidecar", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      jsonResponse({
        conversation: {
          id: "c-1",
          title: "Retention work",
          created_at: "2026-01-01T00:00:00Z",
          updated_at: "2026-01-02T00:00:00Z",
          head_id: "m-2",
        },
      }),
    );

    const renamed = await renameConversation("c-1", "  Retention work  ");

    expect(renamed.title).toBe("Retention work");
    const [url, init] = vi.mocked(fetch).mock.calls[0] as [string, RequestInit];
    expect(String(url)).toContain("/api/conversations/c-1");
    expect(init.method).toBe("PATCH");
    // The branch is not in the body: a rename must not move the reader.
    expect(JSON.parse(String(init.body))).toEqual({ title: "Retention work" });
    expect(bff.memory.renameConversation).not.toHaveBeenCalled();
  });

  it("renames through the browser store when the sidecar is unreachable", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      jsonResponse({ detail: "Sidecar unreachable" }, 502),
    );
    vi.mocked(bff.memory.renameConversation).mockResolvedValueOnce({
      id: "c-1",
      title: "Retention work",
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-02T00:00:00Z",
      head_id: null,
    });

    const renamed = await renameConversation("c-1", "Retention work");

    expect(renamed.title).toBe("Retention work");
    expect(bff.memory.renameConversation).toHaveBeenCalledWith("c-1", "Retention work");
  });

  it("refuses a blank name before any request", async () => {
    await expect(renameConversation("c-1", "   ")).rejects.toThrow(/name/i);

    expect(fetch).not.toHaveBeenCalled();
    expect(bff.memory.renameConversation).not.toHaveBeenCalled();
  });
});
