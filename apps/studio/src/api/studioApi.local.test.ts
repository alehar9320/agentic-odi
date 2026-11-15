import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { StudioApiError, addEvidence, addOutcome, addStep, createJob, deleteEvidence, fetchCanvas, fetchMemory, isTransportFailure, listConversations, streamChat } from "./studioApi";
import type { OutboxRecord } from "../bff/store/types";

const outbox: OutboxRecord[] = [];

const bff = {
  data: { fetchCanvas: vi.fn() },
  memory: { listObservations: vi.fn(), listConversations: vi.fn() },
  chat: { stream: vi.fn() },
  createJob: vi.fn(),
  addStep: vi.fn(),
  addOutcome: vi.fn(),
  updateOutcome: vi.fn(),
  deleteOutcome: vi.fn(),
  addEvidence: vi.fn(),
  deleteEvidence: vi.fn(),
  listOutbox: vi.fn(async () => outbox),
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

/** A static host that answered an `/api` call with the SPA shell, not JSON. */
function htmlResponse(status = 200): Response {
  return new Response("<!doctype html><html></html>", {
    status,
    headers: { "Content-Type": "text/html; charset=utf-8" },
  });
}

/** A sidecar that is not there: a proxy that answers 503 with no structured error. */
function offlineResponse(): Response {
  return new Response(JSON.stringify({ detail: "Sidecar unreachable" }), {
    status: 503,
    headers: { "Content-Type": "application/json" },
  });
}

function outboxRecord(overrides: Partial<OutboxRecord>): OutboxRecord {
  return {
    id: "rec",
    kind: "create",
    entity: "job",
    local_id: null,
    server_id: null,
    payload: {},
    depends_on: [],
    state: "pending",
    attempts: 0,
    last_error: null,
    created_at: "2026-01-01T00:00:00.000Z",
    acknowledged_at: null,
    ...overrides,
  };
}

beforeEach(() => {
  outbox.length = 0;
  vi.stubGlobal("fetch", vi.fn(async () => jsonResponse({})));
  vi.mocked(bff.data.fetchCanvas).mockReset();
  vi.mocked(bff.memory.listObservations).mockReset();
  vi.mocked(bff.memory.listConversations).mockReset();
  vi.mocked(bff.chat.stream).mockReset();
  vi.mocked(bff.createJob).mockReset();
  vi.mocked(bff.addStep).mockReset();
  vi.mocked(bff.addOutcome).mockReset();
  vi.mocked(bff.addEvidence).mockReset();
  vi.mocked(bff.deleteEvidence).mockReset();
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

  it("treats a Worker-generated 502 carrying origin proxy as transport", () => {
    expect(
      isTransportFailure(
        new StudioApiError(
          { code: "mcp_unreachable", message: "down", retryable: true, origin: "proxy" },
          502,
          true,
        ),
      ),
    ).toBe(true);
  });

  it("does not treat a sidecar 502 without origin proxy as transport", () => {
    expect(
      isTransportFailure(
        new StudioApiError({ code: "mcp_unreachable", message: "down", retryable: true }, 502, true),
      ),
    ).toBe(false);
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

  it("falls back to the local BFF for a Worker 502 that marks origin proxy", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      jsonResponse({ error: { code: "mcp_unreachable", message: "down", retryable: true, origin: "proxy" } }, 502),
    );
    vi.mocked(bff.data.fetchCanvas).mockResolvedValueOnce({ jobs: [], steps: [], outcomes: [], source: "local" });

    const canvas = await fetchCanvas("http://mcp");
    expect(canvas.source).toBe("local");
    expect(bff.data.fetchCanvas).toHaveBeenCalled();
  });

  it("does not fall back for a sidecar 502 that does not mark origin proxy", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      jsonResponse({ error: { code: "mcp_unreachable", message: "down", retryable: true } }, 502),
    );
    await expect(fetchCanvas("http://mcp")).rejects.toThrow();
    expect(bff.data.fetchCanvas).not.toHaveBeenCalled();
  });

  it("falls back to the local BFF when a static host answers 200 text/html", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(htmlResponse());
    vi.mocked(bff.data.fetchCanvas).mockResolvedValueOnce({ jobs: [], steps: [], outcomes: [], source: "local" });

    const canvas = await fetchCanvas("http://mcp");
    expect(canvas.source).toBe("local");
    expect(bff.data.fetchCanvas).toHaveBeenCalled();
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

  it("falls back to the local BFF when a static host answers 200 text/html", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(htmlResponse());
    vi.mocked(bff.chat.stream).mockResolvedValueOnce(undefined);

    await streamChat({ base_url: "", api_key: "", model: "", mcp_url: "", messages: [] }, () => {});
    expect(bff.chat.stream).toHaveBeenCalled();
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

describe("queued writes with no sidecar", () => {
  it("creates a job, a step, and an outcome locally and marks each pending", async () => {
    // /api answers 503 with no structured error: the sidecar is not there. Every
    // write must succeed locally and come back marked pending, never as a failure.
    vi.mocked(fetch).mockResolvedValue(offlineResponse());
    vi.mocked(bff.createJob).mockResolvedValue({ id: "j-1", name: "Job", description: "" });
    vi.mocked(bff.addStep).mockResolvedValue({ id: "s-1", job_id: "j-1", name: "Step", order: 1 });
    vi.mocked(bff.addOutcome).mockResolvedValue({
      id: "o-1",
      job_id: "j-1",
      statement: "Minimize the time",
      importance: 8,
      satisfaction: 3,
      opportunity_score: 13,
    });

    const job = await createJob({ name: "Job", mcp_url: "http://mcp" });
    const step = await addStep({ mcp_url: "http://mcp", job_id: job.id, name: "Step", order: 1 });
    const outcome = await addOutcome({
      mcp_url: "http://mcp",
      job_id: job.id,
      statement: "Minimize the time",
      importance: 8,
      satisfaction: 3,
    });

    expect(job).toMatchObject({ id: "j-1", pending: true });
    expect(step).toMatchObject({ id: "s-1", pending: true });
    expect(outcome).toMatchObject({ id: "o-1", pending: true });
    expect(bff.createJob).toHaveBeenCalledWith({ name: "Job", description: undefined });
    expect(bff.addStep).toHaveBeenCalledWith({ job_id: "j-1", name: "Step", order: 1 });
    expect(bff.addOutcome).toHaveBeenCalledWith({
      job_id: "j-1",
      statement: "Minimize the time",
      importance: 8,
      satisfaction: 3,
    });
  });

  it("records a capture in the browser store when the sidecar is down", async () => {
    // The sidecar is not there. A capture must still land locally and come back
    // `ok`, never as a failure, so the person's evidence is not lost.
    vi.mocked(fetch).mockResolvedValue(offlineResponse());
    vi.mocked(bff.addEvidence).mockResolvedValue({ id: "e-1", name: "Call notes" });

    const result = await addEvidence({
      mcp_url: "http://mcp",
      source_name: "Support inbox",
      name: "Call notes",
      content: "They churn on deploy time",
      job_id: "j-1",
    });

    expect(result).toEqual({ ok: true, pending: true });
    expect(bff.addEvidence).toHaveBeenCalledWith({
      source_name: "Support inbox",
      source_kind: undefined,
      item_type: undefined,
      name: "Call notes",
      content: "They churn on deploy time",
      url: undefined,
      job_id: "j-1",
      step_id: undefined,
      outcome_id: undefined,
    });
  });

  it("removes a capture from the browser store when the sidecar is down", async () => {
    vi.mocked(fetch).mockResolvedValue(offlineResponse());
    vi.mocked(bff.deleteEvidence).mockResolvedValue({ deleted: "e-1" });

    const result = await deleteEvidence("e-1", "http://mcp");

    expect(result).toEqual({ ok: true, pending: true });
    expect(bff.deleteEvidence).toHaveBeenCalledWith("e-1");
  });

  it("serves the sidecar's receipt, not the local one, while the sidecar answers", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse({ ok: true }));

    const result = await addEvidence({
      mcp_url: "http://mcp",
      source_name: "Support inbox",
      name: "Call notes",
      content: "They churn on deploy time",
    });

    expect(result).toEqual({ ok: true });
    expect(bff.addEvidence).not.toHaveBeenCalled();
  });

  it("does not queue a sidecar 422 for a capture", async () => {
    vi.mocked(fetch).mockResolvedValue(
      jsonResponse({ error: { code: "validation", message: "bad", retryable: false } }, 422),
    );

    await expect(
      addEvidence({
        mcp_url: "http://mcp",
        source_name: "Support inbox",
        name: "",
        content: "x",
      }),
    ).rejects.toThrow();

    expect(bff.addEvidence).not.toHaveBeenCalled();
  });

  it("does not queue an application error from a live sidecar", async () => {
    vi.mocked(fetch).mockResolvedValue(
      jsonResponse({ error: { code: "validation", message: "bad", retryable: false } }, 422),
    );

    await expect(
      addOutcome({
        mcp_url: "http://mcp",
        job_id: "j-1",
        statement: "bad",
        importance: 8,
        satisfaction: 3,
      }),
    ).rejects.toThrow();

    expect(bff.addOutcome).not.toHaveBeenCalled();
  });

  it("does not queue a sidecar 409 conflict", async () => {
    vi.mocked(fetch).mockResolvedValue(
      jsonResponse({ error: { code: "conflict", message: "changed", retryable: false } }, 409),
    );

    await expect(
      addStep({ mcp_url: "http://mcp", job_id: "j-1", name: "Step", order: 1 }),
    ).rejects.toThrow();

    expect(bff.addStep).not.toHaveBeenCalled();
  });

  it("serves the sidecar's record, not the local one, while the sidecar answers", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse({ id: "server-o", statement: "From the sidecar" }));

    const outcome = await addOutcome({
      mcp_url: "http://mcp",
      job_id: "j-1",
      statement: "Minimize the time",
      importance: 8,
      satisfaction: 3,
    });

    expect(outcome).toMatchObject({ id: "server-o" });
    expect((outcome as { pending?: boolean }).pending).toBeUndefined();
    expect(bff.addOutcome).not.toHaveBeenCalled();
  });
});

describe("canvas reads keep a queued write visible", () => {
  it("overlays a pending outcome on a canvas the sidecar answered without it", async () => {
    // The sidecar answers a refresh with a canvas that predates the queued write.
    // The optimistic outcome must still be on the board, marked pending.
    vi.mocked(fetch).mockResolvedValueOnce(
      jsonResponse({ jobs: [], steps: [], outcomes: [], source: "mcp" }),
    );
    outbox.push(
      outboxRecord({
        kind: "create",
        entity: "outcome",
        local_id: "o-1",
        payload: {
          job_id: "j-1",
          statement: "Minimize the time",
          importance: 8,
          satisfaction: 3,
        },
      }),
    );

    const canvas = await fetchCanvas("http://mcp");

    const outcome = canvas.outcomes.find((item) => item.id === "o-1");
    expect(outcome).toBeDefined();
    expect(outcome?.pending).toBe(true);
    expect(outcome?.opportunity_score).toBe(13);
  });

  it("marks a pending edit on a row the sidecar returned unmarked", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      jsonResponse({
        jobs: [{ id: "j-1", name: "Job" }],
        steps: [],
        outcomes: [],
        source: "mcp",
      }),
    );
    outbox.push(outboxRecord({ kind: "update", entity: "job", local_id: "j-1", payload: {} }));

    const canvas = await fetchCanvas("http://mcp");

    expect(canvas.jobs.find((job) => job.id === "j-1")?.pending).toBe(true);
  });

  it("hides a row whose delete is still queued", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      jsonResponse({
        jobs: [{ id: "j-1", name: "Job" }],
        steps: [],
        outcomes: [],
        source: "mcp",
      }),
    );
    outbox.push(outboxRecord({ kind: "delete", entity: "job", local_id: "j-1", payload: {} }));

    const canvas = await fetchCanvas("http://mcp");

    expect(canvas.jobs).toHaveLength(0);
  });

  it("leaves an acknowledged record off the overlay", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      jsonResponse({ jobs: [], steps: [], outcomes: [], source: "mcp" }),
    );
    outbox.push(
      outboxRecord({
        kind: "create",
        entity: "outcome",
        local_id: "o-1",
        state: "acknowledged",
        payload: { job_id: "j-1", statement: "x", importance: 8, satisfaction: 3 },
      }),
    );

    const canvas = await fetchCanvas("http://mcp");

    expect(canvas.outcomes).toHaveLength(0);
  });

  it("overlays a queued capture on a canvas the sidecar answered without it", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      jsonResponse({
        jobs: [],
        steps: [],
        outcomes: [],
        evidence: [],
        source: "mcp",
        provenance: {
          kind: "live",
          reason: "store",
          generated_at: "2026-11-01T12:00:00.000Z",
          record_counts: { jobs: 0, steps: 0, outcomes: 0, evidence: 0 },
        },
      }),
    );
    outbox.push(
      outboxRecord({
        kind: "create",
        entity: "evidence",
        local_id: "e-1",
        payload: {
          source_name: "Support inbox",
          name: "Call notes",
          content: "They churn on deploy time",
          job_id: "j-1",
        },
      }),
    );

    const canvas = await fetchCanvas("http://mcp");

    const record = canvas.evidence?.find((item) => item.id === "e-1");
    expect(record).toBeDefined();
    expect(record?.pending).toBe(true);
    expect(record?.name).toBe("Call notes");
    expect(record?.job_id).toBe("j-1");
    // The board must say the browser holds the capture, not claim the server does.
    expect(canvas.provenance?.kept_by_browser).toBe(true);
  });

  it("hides a capture whose delete is still queued", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      jsonResponse({
        jobs: [],
        steps: [],
        outcomes: [],
        evidence: [{ id: "e-1", name: "Call notes" }],
        source: "mcp",
      }),
    );
    outbox.push(
      outboxRecord({ kind: "delete", entity: "evidence", local_id: "e-1", payload: {} }),
    );

    const canvas = await fetchCanvas("http://mcp");

    expect(canvas.evidence ?? []).toHaveLength(0);
  });
});
