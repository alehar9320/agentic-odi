import { afterEach, describe, expect, it, vi } from "vitest";

import {
  addConnector,
  addObservation,
  addOutcome,
  addStep,
  checkConnectorHealth,
  clearMemory,
  createConversation,
  deleteConnector,
  deleteObservation,
  fetchLatestConversation,
  fetchMemory,
  updateObservation,
  fetchCanvas,
  fetchChangelog,
  fetchConfig,
  fetchConnectorCatalog,
  fetchConnectors,
  healthLlm,
  healthMcp,
  streamChat,
  asStudioError,
} from "./studioApi";

afterEach(() => {
  vi.unstubAllGlobals();
});

function mockJson(body: unknown): void {
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async () =>
        new Response(JSON.stringify(body), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
    ),
  );
}

describe("fetchConfig", () => {
  it("returns the env-derived defaults", async () => {
    mockJson({
      defaults: { base_url: "http://llm", api_key: "k", model_name: "m", mcp_url: "u" },
    });

    await expect(fetchConfig()).resolves.toMatchObject({
      base_url: "http://llm",
      model_name: "m",
    });
  });
});

describe("fetchChangelog", () => {
  it("returns the parsed changelog data", async () => {
    mockJson({ releases: [{ version: "0.8.0", date: "2026-10-20", categories: [] }] });

    const data = await fetchChangelog();
    expect(data.releases[0].version).toBe("0.8.0");
  });
});

describe("fetchCanvas", () => {
  it("returns jobs/steps/outcomes with the source label", async () => {
    mockJson({ jobs: [{ id: "JOB-402" }], steps: [], outcomes: [], source: "seed" });

    const canvas = await fetchCanvas("http://mcp/mcp");

    expect(canvas.source).toBe("seed");
    expect(canvas.jobs[0].id).toBe("JOB-402");
  });
});

describe("health probes", () => {
  it("returns mcp reachability", async () => {
    mockJson({ reachable: false });
    await expect(healthMcp("http://mcp/mcp")).resolves.toEqual({ reachable: false });
  });

  it("returns llm health", async () => {
    mockJson({ healthy: true, message: "ok" });
    await expect(
      healthLlm({ base_url: "u", api_key: "k", model: "m" }),
    ).resolves.toEqual({ healthy: true, message: "ok" });
  });
});

describe("mcp passthrough writes", () => {
  it("adds a step", async () => {
    mockJson({ id: "STEP-1", job_id: "JOB-402", name: "9. Ship", order: 9 });
    await expect(
      addStep({ mcp_url: "u", job_id: "JOB-402", name: "9. Ship", order: 9 }),
    ).resolves.toMatchObject({ id: "STEP-1" });
  });

  it("adds an outcome", async () => {
    mockJson({ id: "O-1", statement: "Minimize time", opportunity_score: 12 });
    await expect(
      addOutcome({
        mcp_url: "u",
        job_id: "JOB-402",
        statement: "Minimize time",
        importance: 8.5,
        satisfaction: 3.5,
      }),
    ).resolves.toMatchObject({ id: "O-1" });
  });
});

describe("streamChat", () => {
  const frame =
    'event: status\ndata: {"phase":"health_check"}\n\n' +
    'event: delta\ndata: {"text":"Hel"}\n\n' +
    'event: delta\ndata: {"text":"lo"}\n\n' +
    'event: message\ndata: {"content":"Hello"}\n\n';

  it("serializes visible messages and attachments to the sidecar request schema", async () => {
    const requestBodies: Record<string, unknown>[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
        requestBodies.push(JSON.parse(String(init?.body ?? "{}")) as Record<string, unknown>);
        return new Response("", {
          status: 200,
          headers: { "Content-Type": "text/event-stream" },
        });
      }),
    );

    await streamChat(
      {
        base_url: "http://llm/v1",
        api_key: "key",
        model: "model",
        mcp_url: "http://mcp",
        messages: [
          { id: "t-1", parentId: null, role: "user", content: "First" },
          { id: "n-1", parentId: "t-1", role: "notice", content: "Local note" },
          { id: "t-2", parentId: "t-1", role: "assistant", content: "Answer" },
          { id: "t-3", parentId: "t-2", role: "user", content: "Follow-up" },
        ],
        attachments: [
          {
            id: "file-1",
            name: "notes.md",
            contentType: "text/markdown",
            size: 15,
            text: "file contents",
            dataUrl: "data:image/png;base64,AAAA",
          },
        ],
      },
      () => {},
    );

    expect(requestBodies[0]?.messages).toEqual([
      { id: "t-1", role: "user", content: "First", parent_id: null },
      { id: "t-2", role: "assistant", content: "Answer", parent_id: "t-1" },
      { id: "t-3", role: "user", content: "Follow-up", parent_id: "t-2" },
    ]);
    expect(requestBodies[0]?.attachments).toEqual([
      {
        name: "notes.md",
        content_type: "text/markdown",
        size: 15,
        text: "file contents",
        data_url: "data:image/png;base64,AAAA",
      },
    ]);
  });

  it("forwards parsed SSE events to the handler in order", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(frame, { status: 200, headers: { "Content-Type": "text/event-stream" } }),
      ),
    );

    const seen: string[] = [];
    await streamChat(
      { base_url: "", api_key: "", model: "", mcp_url: "", messages: [] },
      (event) => seen.push(event.event),
    );

    expect(seen).toEqual(["status", "delta", "delta", "message"]);
  });

  it("displays the server-provided message verbatim (no client-side fallback)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(frame, { status: 200, headers: { "Content-Type": "text/event-stream" } }),
      ),
    );

    let content = "";
    await streamChat(
      { base_url: "", api_key: "", model: "", mcp_url: "", messages: [] },
      (event) => {
        if (event.event === "message") {
          content = String((event.data as { content: string }).content);
        }
      },
    );

    expect(content).toBe("Hello");
  });

  it("raises on a non-ok response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("boom", { status: 500 })),
    );

    await expect(
      streamChat(
        { base_url: "", api_key: "", model: "", mcp_url: "", messages: [] },
        () => {},
      ),
    ).rejects.toThrow();
  });
});

describe("connectors", () => {
  it("fetchConnectorCatalog returns the preset list", async () => {
    mockJson([{ id: "notion", label: "Notion", is_recommended: true }]);

    await expect(fetchConnectorCatalog()).resolves.toMatchObject([{ id: "notion", is_recommended: true }]);
  });

  it("fetchConnectors returns registered connectors", async () => {
    mockJson([{ name: "gong", kind: "mcp", enabled: true }]);

    await expect(fetchConnectors()).resolves.toMatchObject([{ name: "gong", kind: "mcp" }]);
  });

  it("addConnector posts name and url", async () => {
    mockJson({ ok: true, name: "gong" });

    await expect(addConnector({ name: "gong", url: "http://localhost:9000/mcp" })).resolves.toEqual({
      ok: true,
      name: "gong",
    });
    expect(fetch).toHaveBeenCalledWith(
      "/api/connectors",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ name: "gong", url: "http://localhost:9000/mcp" }) }),
    );
  });

  it("deleteConnector sends a DELETE to the named route", async () => {
    mockJson({ ok: true, name: "gong" });

    await deleteConnector("gong");

    expect(fetch).toHaveBeenCalledWith("/api/connectors/gong", expect.objectContaining({ method: "DELETE" }));
  });

  it("checkConnectorHealth posts to the health route", async () => {
    mockJson({ ok: true, message: "ok" });

    await expect(checkConnectorHealth("gong")).resolves.toEqual({ ok: true, message: "ok" });
    expect(fetch).toHaveBeenCalledWith(
      "/api/connectors/gong/health",
      expect.objectContaining({ method: "POST" }),
    );
  });
});


describe("memory", () => {
  const observation = {
    id: "o-1",
    kind: "career",
    text: "Owns activation.",
    data: {},
    status: "suggested",
    confidence: 0.8,
    source_turn: 1,
    created_at: "2026-10-22T10:00:00+00:00",
    updated_at: "2026-10-22T10:00:00+00:00",
  };

  it("fetchMemory unwraps the observations array", async () => {
    mockJson({ observations: [observation] });
    await expect(fetchMemory()).resolves.toEqual([observation]);
    expect(fetch).toHaveBeenCalledWith("/api/memory/observations", expect.objectContaining({ headers: expect.any(Object) }));
  });

  it("addObservation posts the observation", async () => {
    mockJson({ observation });
    await expect(
      addObservation({ kind: "career", text: "Owns activation.", confirmed: true }),
    ).resolves.toEqual(observation);
    expect(fetch).toHaveBeenCalledWith(
      "/api/memory/observations",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ kind: "career", text: "Owns activation.", confirmed: true }),
      }),
    );
  });

  it("updateObservation patches by id", async () => {
    mockJson({ observation: { ...observation, status: "confirmed" } });
    await expect(updateObservation("o-1", { status: "confirmed" })).resolves.toMatchObject({
      status: "confirmed",
    });
    expect(fetch).toHaveBeenCalledWith(
      "/api/memory/observations/o-1",
      expect.objectContaining({ method: "PATCH" }),
    );
  });

  it("deleteObservation and clearMemory send DELETE", async () => {
    mockJson({ ok: true });
    await deleteObservation("o-1");
    expect(fetch).toHaveBeenCalledWith(
      "/api/memory/observations/o-1",
      expect.objectContaining({ method: "DELETE" }),
    );
    await clearMemory();
    expect(fetch).toHaveBeenCalledWith("/api/memory", expect.objectContaining({ method: "DELETE" }));
  });
});

describe("conversations", () => {
  const conversation = {
    id: "c-1",
    title: "Activation",
    created_at: "2026-10-22T10:00:00+00:00",
    updated_at: "2026-10-22T10:00:00+00:00",
  };

  it("fetchLatestConversation returns the conversation and turns", async () => {
    mockJson({ conversation, turns: [{ id: 1, conversation_id: "c-1", role: "user", content: "hi", created_at: "x" }] });
    const latest = await fetchLatestConversation();
    expect(latest.conversation).toEqual(conversation);
    expect(latest.turns).toHaveLength(1);
  });

  it("createConversation unwraps the conversation", async () => {
    mockJson({ conversation });
    await expect(createConversation()).resolves.toEqual(conversation);
    expect(fetch).toHaveBeenCalledWith(
      "/api/conversations",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("streamChat forwards conversation_id", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("", { status: 200, headers: { "Content-Type": "text/event-stream" } })),
    );

    await streamChat(
      {
        base_url: "",
        api_key: "",
        model: "",
        mcp_url: "",
        messages: [],
        conversation_id: "c-1",
      },
      () => {},
    );

    expect(fetch).toHaveBeenCalledWith(
      "/api/chat",
      expect.objectContaining({
        body: expect.stringContaining('"conversation_id":"c-1"'),
      }),
    );
  });
});

describe("typed failures", () => {
  function mockFailure(status: number, body: unknown): void {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(JSON.stringify(body), {
            status,
            headers: { "Content-Type": "application/json" },
          }),
      ),
    );
  }

  it("rejects with a StudioApiError carrying the server's code and suggestion", async () => {
    mockFailure(422, {
      error: {
        code: "out_of_range",
        message: "Importance must be between 1.0 and 10.0",
        detail: "importance: 42",
        suggestion: "Use 1-10.",
        retryable: false,
        request_id: "req-1",
      },
    });

    await expect(
      addOutcome({
        mcp_url: "u",
        job_id: "JOB-402",
        statement: "Minimize time",
        importance: 42,
        satisfaction: 1,
      }),
    ).rejects.toMatchObject({
      name: "StudioApiError",
      error: {
        code: "out_of_range",
        message: "Importance must be between 1.0 and 10.0",
        suggestion: "Use 1-10.",
        request_id: "req-1",
      },
    });
  });

  it("still rejects an old-style detail body with that message", async () => {
    mockFailure(400, { detail: "nope" });

    await expect(
      addStep({ mcp_url: "u", job_id: "JOB-402", name: "9. Ship", order: 9 }),
    ).rejects.toMatchObject({ message: "nope" });
  });

  it("turns an unknown failure into an internal error", async () => {
    mockFailure(500, {});

    await expect(
      addStep({ mcp_url: "u", job_id: "JOB-402", name: "9. Ship", order: 9 }),
    ).rejects.toMatchObject({
      error: { code: "internal" },
    });
  });

  it("exposes asStudioError for non-API failures", () => {
    const problem = asStudioError(new Error("boom"));

    expect(problem.code).toBe("internal");
    expect(problem.message).toBe("boom");
  });

  it("classifies a network failure (sidecar down) as mcp_unreachable with a suggestion", () => {
    const problem = asStudioError(new TypeError("fetch failed"));

    expect(problem.code).toBe("mcp_unreachable");
    expect(problem.retryable).toBe(true);
    expect(problem.suggestion).toMatch(/sidecar/i);
    expect(problem.message).toMatch(/reachable|not running|unreachable/i);
  });

  it("classifies an empty 502 response as mcp_unreachable", async () => {
    mockFailure(502, {});

    await expect(
      addOutcome({
        mcp_url: "u",
        job_id: "JOB-402",
        statement: "Minimize time",
        importance: 5,
        satisfaction: 3,
      }),
     ).rejects.toMatchObject({
       error: { code: "mcp_unreachable", retryable: true, suggestion: expect.stringContaining("sidecar") },
     });
   });

   it("classifies an empty 404 response as not_found", async () => {
    mockFailure(404, {});

    await expect(
      addOutcome({
        mcp_url: "u",
        job_id: "JOB-402",
        statement: "Minimize time",
        importance: 5,
        satisfaction: 3,
      }),
    ).rejects.toMatchObject({ error: { code: "not_found" } });
  });
});
