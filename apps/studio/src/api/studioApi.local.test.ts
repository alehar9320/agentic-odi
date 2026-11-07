import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  StudioApiError,
  addOutcome,
  createJob,
  deleteOutcome,
  fetchCanvas,
  fetchMemory,
  isTransportFailure,
  listConversations,
  streamChat,
  updateJob,
} from "./studioApi";

const bff = {
  data: {
    fetchCanvas: vi.fn(),
    createJob: vi.fn(),
    updateJob: vi.fn(),
    deleteJob: vi.fn(),
    addStep: vi.fn(),
    updateStep: vi.fn(),
    deleteStep: vi.fn(),
    addOutcome: vi.fn(),
    updateOutcome: vi.fn(),
    deleteOutcome: vi.fn(),
  },
  memory: { listObservations: vi.fn(), listConversations: vi.fn() },
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

/** What a dead reverse proxy returns: a status the client trusts, and no JSON. */
function htmlResponse(status = 503): Response {
  return new Response("Service Unavailable", {
    status,
    headers: { "Content-Type": "text/html" },
  });
}

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(async () => jsonResponse({})));
  for (const method of Object.values(bff.data)) {
    method.mockReset();
  }
  vi.mocked(bff.memory.listObservations).mockReset();
  vi.mocked(bff.memory.listConversations).mockReset();
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

  it("treats the hosted Worker's sidecar_unavailable answer as transport", () => {
    expect(
      isTransportFailure(
        new StudioApiError(
          { code: "sidecar_unavailable", message: "No sidecar.", retryable: false },
          502,
          true,
        ),
      ),
    ).toBe(true);
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

describe("canvas writes fall back to the browser store", () => {
  it("creates the job locally and drops the sidecar's mcp_url", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(htmlResponse());
    const job = { id: "job-1", name: "Get a service from commit to production", description: "" };
    vi.mocked(bff.data.createJob).mockResolvedValueOnce(job);

    await expect(
      createJob({ name: "Get a service from commit to production", mcp_url: "http://mcp" }),
    ).resolves.toEqual(job);
    expect(bff.data.createJob).toHaveBeenCalledWith({
      name: "Get a service from commit to production",
    });
  });

  it("records the outcome locally when the proxy answers 503 HTML", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(htmlResponse());
    const outcome = {
      id: "out-1",
      job_id: "job-1",
      statement: "Minimize the time it takes to rotate secrets",
      importance: 9,
      satisfaction: 3,
      opportunity_score: 15,
    };
    vi.mocked(bff.data.addOutcome).mockResolvedValueOnce(outcome);

    await expect(
      addOutcome({
        job_id: "job-1",
        statement: "Minimize the time it takes to rotate secrets",
        importance: 9,
        satisfaction: 3,
        mcp_url: "http://mcp",
      }),
    ).resolves.toEqual(outcome);
    expect(bff.data.addOutcome).toHaveBeenCalledWith({
      job_id: "job-1",
      statement: "Minimize the time it takes to rotate secrets",
      importance: 9,
      satisfaction: 3,
    });
  });

  it("falls back when the hosted Worker says sidecar_unavailable", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      jsonResponse(
        { error: { code: "sidecar_unavailable", message: "No sidecar.", retryable: false } },
        502,
      ),
    );
    vi.mocked(bff.data.updateJob).mockResolvedValueOnce({ id: "job-1", name: "Renamed" });

    await updateJob("job-1", { name: "Renamed", mcp_url: "http://mcp" });
    expect(bff.data.updateJob).toHaveBeenCalledWith("job-1", { name: "Renamed" });
  });

  it("deletes the outcome locally", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(htmlResponse());
    vi.mocked(bff.data.deleteOutcome).mockResolvedValueOnce({ deleted: "out-1" });

    await expect(deleteOutcome("out-1", "http://mcp")).resolves.toEqual({ deleted: "out-1" });
    expect(bff.data.deleteOutcome).toHaveBeenCalledWith("out-1");
  });

  it("does not save a write the live sidecar rejected as invalid", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      jsonResponse({ error: { code: "validation", message: "Job name cannot be empty." } }, 422),
    );

    await expect(createJob({ name: "   ", mcp_url: "http://mcp" })).rejects.toThrow();
    expect(bff.data.createJob).not.toHaveBeenCalled();
  });

  it("does not save a write when the sidecar cannot reach its MCP server", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      jsonResponse(
        { error: { code: "mcp_unreachable", message: "The MCP server could not be reached.", retryable: true } },
        502,
      ),
    );

    await expect(
      addOutcome({
        job_id: "job-1",
        statement: "Anything",
        importance: 5,
        satisfaction: 5,
        mcp_url: "http://mcp",
      }),
    ).rejects.toThrow();
    expect(bff.data.addOutcome).not.toHaveBeenCalled();
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
