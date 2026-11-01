import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  StudioApiError,
  addOutcome,
  addStep,
  createJob,
  deleteJob,
  deleteOutcome,
  deleteStep,
  fetchCanvas,
  fetchMemory,
  isTransportFailure,
  streamChat,
  updateJob,
  updateOutcome,
  updateStep,
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

/**
 * The Worker's own answer for a deployment with `SIDECAR_URL` unset — GET
 * https://agentic-odi.alehar.workers.dev/api/canvas returned this shape at 502
 * on 2026-11-01, carrying `mcp_unreachable` until the Worker was given a code of
 * its own. A structured body is the trap: it is how the studio says "I heard you
 * and refused", so the code is the only thing that can say whether a sidecar
 * refused the request or no sidecar exists at all.
 */
const WORKER_ANSWER = {
  error: {
    code: "sidecar_unavailable",
    message: "The studio sidecar isn't configured.",
    suggestion: "Set SIDECAR_URL and redeploy.",
    retryable: false,
    request_id: null,
  },
};

function workerAnswer(): Response {
  return jsonResponse(WORKER_ANSWER, 502);
}

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(async () => jsonResponse({})));
  for (const method of Object.values(bff.data)) {
    method.mockReset();
  }
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

describe("the hosted Worker's own answer", () => {
  it("is a transport failure, because nothing downstream can take the request", () => {
    expect(
      isTransportFailure(
        new StudioApiError(
          {
            code: "sidecar_unavailable",
            message: "The studio sidecar isn't configured.",
            retryable: false,
          },
          502,
          true,
        ),
      ),
    ).toBe(true);
  });

  it("hands the canvas to the browser store rather than showing a failure", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(workerAnswer());
    vi.mocked(bff.data.fetchCanvas).mockResolvedValueOnce({
      jobs: [],
      steps: [],
      outcomes: [],
      source: "local",
    });

    const canvas = await fetchCanvas("http://mcp");

    expect(canvas.source).toBe("local");
    expect(bff.data.fetchCanvas).toHaveBeenCalled();
  });

  it("hands the turn to the browser assistant", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(workerAnswer());
    vi.mocked(bff.chat.stream).mockResolvedValueOnce(undefined);

    await streamChat({ base_url: "", api_key: "", model: "", mcp_url: "", messages: [] }, () => {});

    expect(bff.chat.stream).toHaveBeenCalled();
  });

  it("still treats the sidecar's own unreachable-MCP answer as a real failure", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      jsonResponse(
        {
          error: {
            code: "mcp_unreachable",
            message: "The MCP server could not be reached.",
            retryable: true,
          },
        },
        502,
      ),
    );

    await expect(fetchCanvas("http://mcp")).rejects.toThrow();
    expect(bff.data.fetchCanvas).not.toHaveBeenCalled();
  });
});

describe("canvas writes on a hosted studio with no sidecar", () => {
  /**
   * Capturing an outcome is the one thing a first-time visitor must be able to
   * do, and until now every write went to the sidecar and nowhere else: a
   * visitor with no server lost the words they had just typed. Reads already
   * fell back, so this is the half that makes the studio genuinely usable.
   *
   * `mcp_url` is part of the sidecar payload and is dropped on the way in — the
   * browser store has no server to address.
   */
  it("creates the job in the browser store", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(workerAnswer());
    const job = { id: "job-1", name: "Get a service from commit to production", description: "" };
    vi.mocked(bff.data.createJob).mockResolvedValueOnce(job);

    await expect(
      createJob({ name: "Get a service from commit to production", mcp_url: "http://mcp" }),
    ).resolves.toEqual(job);
    expect(bff.data.createJob).toHaveBeenCalledWith({
      name: "Get a service from commit to production",
    });
  });

  it("updates the job in the browser store", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(workerAnswer());
    vi.mocked(bff.data.updateJob).mockResolvedValueOnce({
      id: "job-1",
      name: "Renamed job",
      description: "Platform engineers",
    });

    await updateJob("job-1", { name: "Renamed job", mcp_url: "http://mcp" });
    expect(bff.data.updateJob).toHaveBeenCalledWith("job-1", { name: "Renamed job" });
  });

  it("deletes the job in the browser store", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(workerAnswer());
    vi.mocked(bff.data.deleteJob).mockResolvedValueOnce({ deleted: "job-1" });

    await expect(deleteJob("job-1", "http://mcp")).resolves.toEqual({ deleted: "job-1" });
    expect(bff.data.deleteJob).toHaveBeenCalledWith("job-1");
  });

  it("adds the step in the browser store", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(workerAnswer());
    const step = { id: "step-1", job_id: "job-1", name: "Open the pull request", order: 2 };
    vi.mocked(bff.data.addStep).mockResolvedValueOnce(step);

    await expect(
      addStep({ job_id: "job-1", name: "Open the pull request", order: 2, mcp_url: "http://mcp" }),
    ).resolves.toEqual(step);
    expect(bff.data.addStep).toHaveBeenCalledWith({
      job_id: "job-1",
      name: "Open the pull request",
      order: 2,
    });
  });

  it("updates the step in the browser store", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(workerAnswer());
    vi.mocked(bff.data.updateStep).mockResolvedValueOnce({
      id: "step-1",
      job_id: "job-1",
      name: "Open the merge request",
      order: 3,
    });

    await updateStep("step-1", { name: "Open the merge request", order: 3, mcp_url: "http://mcp" });
    expect(bff.data.updateStep).toHaveBeenCalledWith("step-1", {
      name: "Open the merge request",
      order: 3,
    });
  });

  it("deletes the step in the browser store", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(workerAnswer());
    vi.mocked(bff.data.deleteStep).mockResolvedValueOnce({ deleted: "step-1" });

    await expect(deleteStep("step-1", "http://mcp")).resolves.toEqual({ deleted: "step-1" });
    expect(bff.data.deleteStep).toHaveBeenCalledWith("step-1");
  });

  it("records the outcome in the browser store", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(workerAnswer());
    const outcome = {
      id: "out-1",
      job_id: "job-1",
      statement: "Minimize the time from merge to production",
      importance: 9,
      satisfaction: 3,
      opportunity_score: 15,
    };
    vi.mocked(bff.data.addOutcome).mockResolvedValueOnce(outcome);

    await expect(
      addOutcome({
        job_id: "job-1",
        statement: "Minimize the time from merge to production",
        importance: 9,
        satisfaction: 3,
        mcp_url: "http://mcp",
      }),
    ).resolves.toEqual(outcome);
    expect(bff.data.addOutcome).toHaveBeenCalledWith({
      job_id: "job-1",
      statement: "Minimize the time from merge to production",
      importance: 9,
      satisfaction: 3,
    });
  });

  it("updates the outcome in the browser store", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(workerAnswer());
    vi.mocked(bff.data.updateOutcome).mockResolvedValueOnce({
      id: "out-1",
      job_id: "job-1",
      statement: "Minimize lead time for one team",
      importance: 8,
      satisfaction: 3,
      opportunity_score: 13,
    });

    await updateOutcome("out-1", {
      statement: "Minimize lead time for one team",
      importance: 8,
      mcp_url: "http://mcp",
    });
    expect(bff.data.updateOutcome).toHaveBeenCalledWith("out-1", {
      statement: "Minimize lead time for one team",
      importance: 8,
    });
  });

  it("deletes the outcome in the browser store", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(workerAnswer());
    vi.mocked(bff.data.deleteOutcome).mockResolvedValueOnce({ deleted: "out-1" });

    await expect(deleteOutcome("out-1", "http://mcp")).resolves.toEqual({ deleted: "out-1" });
    expect(bff.data.deleteOutcome).toHaveBeenCalledWith("out-1");
  });

  /**
   * The fallback is for a studio that is not there, not for a studio that said
   * no. A live sidecar that rejects the write is the user's own problem — a
   * score out of range, a missing job — and saving it to IndexedDB instead would
   * hide the reason and leave two copies of the truth.
   */
  it("does not save a job the live sidecar refused as invalid", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      jsonResponse({ error: { code: "validation", message: "Job name cannot be empty.", retryable: false } }, 422),
    );

    await expect(createJob({ name: "   ", mcp_url: "http://mcp" })).rejects.toThrow();
    expect(bff.data.createJob).not.toHaveBeenCalled();
  });

  it("does not record an outcome when the sidecar cannot reach its MCP server", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      jsonResponse(
        { error: { code: "mcp_unreachable", message: "The MCP server could not be reached.", retryable: true } },
        502,
      ),
    );

    await expect(
      addOutcome({ job_id: "job-1", statement: "Anything", importance: 5, satisfaction: 5, mcp_url: "http://mcp" }),
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
