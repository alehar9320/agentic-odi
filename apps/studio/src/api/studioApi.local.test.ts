import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { StudioApiError, fetchCanvas, fetchChangelog, fetchMemory, isTransportFailure, streamChat } from "./studioApi";

const bff = {
  fetchChangelog: vi.fn(),
  data: { fetchCanvas: vi.fn() },
  memory: { listObservations: vi.fn() },
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
  vi.mocked(bff.fetchChangelog).mockReset();
  vi.mocked(bff.data.fetchCanvas).mockReset();
  vi.mocked(bff.memory.listObservations).mockReset();
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

describe("fetchChangelog fallback", () => {
  it("falls back to the local BFF when the sidecar returns 502", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse({ detail: "Sidecar unreachable" }, 502));
    vi.mocked(bff.fetchChangelog).mockResolvedValueOnce({ releases: [] });

    const changelog = await fetchChangelog();
    expect(changelog.releases).toEqual([]);
    expect(bff.fetchChangelog).toHaveBeenCalled();
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
