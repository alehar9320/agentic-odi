import { afterEach, describe, expect, it, vi } from "vitest";

import {
  addConnector,
  addOutcome,
  addStep,
  checkConnectorHealth,
  deleteConnector,
  fetchCanvas,
  fetchConfig,
  fetchConnectorCatalog,
  fetchConnectors,
  healthLlm,
  healthMcp,
  streamChat,
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
    mockJson({ ok: true, result: "created" });
    await expect(
      addStep({ mcp_url: "u", job_id: "JOB-402", name: "9. Ship", order: 9 }),
    ).resolves.toMatchObject({ ok: true });
  });

  it("adds an outcome", async () => {
    mockJson({ ok: true, result: "created" });
    await expect(
      addOutcome({
        mcp_url: "u",
        job_id: "JOB-402",
        statement: "Minimize time",
        importance: 8.5,
        satisfaction: 3.5,
      }),
    ).resolves.toMatchObject({ ok: true });
  });
});

describe("streamChat", () => {
  const frame =
    'event: status\ndata: {"phase":"health_check"}\n\n' +
    'event: delta\ndata: {"text":"Hel"}\n\n' +
    'event: delta\ndata: {"text":"lo"}\n\n' +
    'event: message\ndata: {"content":"Hello"}\n\n';

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
