import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { capabilityRegistry } from "./registry";

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response("", { status: 404 })),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("CapabilityRegistry", () => {
  it("always reports local capabilities as available", async () => {
    const statuses = await capabilityRegistry.statuses({
      base_url: "http://localhost:8001/v1",
      api_key: "local",
      model_name: "local-tools-model",
      mcp_url: "http://localhost:8000/mcp",
      theme: "dark",
    });

    const byId = Object.fromEntries(statuses.map((c) => [c.id, c]));
    expect(byId["local-data"].status).toBe("available");
    expect(byId["local-memory"].status).toBe("available");
    expect(byId["deterministic-assistant"].status).toBe("available");
  });

  it("reports endpoint-model as unavailable when the settings name no usable endpoint", async () => {
    const statuses = await capabilityRegistry.statuses({
      base_url: "https://api.example.com/v1",
      api_key: "",
      model_name: "",
      mcp_url: "http://localhost:8000/mcp",
      theme: "dark",
    });
    const byId = Object.fromEntries(statuses.map((c) => [c.id, c]));
    expect(byId["endpoint-model"].status).toBe("unavailable");
  });

  it("never reports a configured endpoint as available before it answers (#515)", async () => {
    const statuses = await capabilityRegistry.statuses({
      base_url: "https://api.example.com/v1",
      api_key: "sk-test",
      model_name: "gpt-4o",
      mcp_url: "http://localhost:8000/mcp",
      theme: "dark",
    });
    const byId = Object.fromEntries(statuses.map((c) => [c.id, c]));
    // Configuration is not evidence that a model answers: the honest answer is
    // "configured, not checked", never "available".
    expect(byId["endpoint-model"].status).toBe("unknown");
    expect(byId["endpoint-model"].label).toBe("Configured");
  });

  it("reports a configured private-network endpoint the same way", async () => {
    const statuses = await capabilityRegistry.statuses({
      base_url: "http://192.168.1.10:11434/v1",
      api_key: "",
      model_name: "llama3",
      mcp_url: "http://localhost:8000/mcp",
      theme: "dark",
    });
    const byId = Object.fromEntries(statuses.map((c) => [c.id, c]));
    expect(byId["endpoint-model"].status).toBe("unknown");
  });

  it("probes MCP with the POST its route accepts, carrying the configured url (#515)", async () => {
    const calls: Array<{ input: RequestInfo | URL; init?: RequestInit }> = [];
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      calls.push({ input, init });
      if (String(input).includes("/api/health/mcp")) {
        return new Response(JSON.stringify({ reachable: true }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      return new Response("", { status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);

    const statuses = await capabilityRegistry.statuses({
      base_url: "http://localhost:8001/v1",
      api_key: "local",
      model_name: "local-tools-model",
      mcp_url: "http://localhost:8000/mcp",
      theme: "dark",
    });

    const byId = Object.fromEntries(statuses.map((c) => [c.id, c]));
    expect(byId["sidecar-mcp"].status).toBe("available");

    const call = calls.find(({ input }) => String(input).includes("/api/health/mcp"));
    expect(call?.init).toMatchObject({
      method: "POST",
      body: JSON.stringify({ mcp_url: "http://localhost:8000/mcp" }),
    });
  });

  it("reports MCP unavailable when the sidecar answered but the server did not", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        if (String(input).includes("/api/health/mcp")) {
          return new Response(JSON.stringify({ reachable: false }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }
        return new Response("", { status: 404 });
      }),
    );

    const statuses = await capabilityRegistry.statuses({
      base_url: "http://localhost:8001/v1",
      api_key: "local",
      model_name: "local-tools-model",
      mcp_url: "http://localhost:8000/mcp",
      theme: "dark",
    });

    const byId = Object.fromEntries(statuses.map((c) => [c.id, c]));
    expect(byId["sidecar-mcp"].status).toBe("unavailable");
  });

  it("reports sidecar capabilities as unavailable when unreachable", async () => {
    const statuses = await capabilityRegistry.statuses({
      base_url: "http://localhost:8001/v1",
      api_key: "local",
      model_name: "local-tools-model",
      mcp_url: "http://localhost:8000/mcp",
      theme: "dark",
    });
    const byId = Object.fromEntries(statuses.map((c) => [c.id, c]));
    expect(byId["sidecar-llm"].status).toBe("unavailable");
    expect(byId["sidecar-connectors"].status).toBe("unavailable");
    expect(byId["sidecar-mcp"].status).toBe("unavailable");
    expect(byId["sidecar-import"].status).toBe("unavailable");
  });

  it("marks sidecar capabilities available when same-origin routes respond OK", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes("/api/capabilities")) {
          return new Response(
            JSON.stringify({
              capabilities: [
                { id: "sidecar-llm", available: true },
                { id: "sidecar-import", available: true },
              ],
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          );
        }
        if (url.includes("/api/health/mcp")) {
          return new Response(JSON.stringify({ reachable: true }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }
        if (url.includes("/api/connectors")) {
          return new Response("", { status: 200 });
        }
        return new Response("", { status: 404 });
      }),
    );
    const statuses = await capabilityRegistry.statuses({
      base_url: "http://localhost:8001/v1",
      api_key: "local",
      model_name: "local-tools-model",
      mcp_url: "http://localhost:8000/mcp",
      theme: "dark",
    });
    const byId = Object.fromEntries(statuses.map((c) => [c.id, c]));
    expect(byId["sidecar-llm"].status).toBe("available");
    expect(byId["sidecar-connectors"].status).toBe("available");
    expect(byId["sidecar-mcp"].status).toBe("available");
    expect(byId["sidecar-import"].status).toBe("available");
  });

  it("presents the bearer token when probing the sidecar", async () => {
    localStorage.setItem("studio.token", "probe-token");
    // The gated sidecar answers only the requests that carry the key, so a
    // probe that forgets it reports the capability as missing.
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const headers = new Headers(init?.headers);
        if (headers.get("Authorization") !== "Bearer probe-token") {
          return new Response("", { status: 401 });
        }
        const url = String(input);
        if (url.includes("/api/capabilities")) {
          return new Response(
            JSON.stringify({
              capabilities: [
                { id: "sidecar-llm", available: true },
                { id: "sidecar-import", available: true },
              ],
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          );
        }
        if (url.includes("/api/health/mcp")) {
          // #515: the MCP probe reads the body's `reachable`; a bare 200 proves
          // the sidecar answered, not that the MCP server did.
          return new Response(JSON.stringify({ reachable: true }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }
        if (url.includes("/api/connectors")) {
          return new Response("", { status: 200 });
        }
        return new Response("", { status: 404 });
      }),
    );
    const statuses = await capabilityRegistry.statuses({
      base_url: "http://localhost:8001/v1",
      api_key: "local",
      model_name: "local-tools-model",
      mcp_url: "http://localhost:8000/mcp",
      theme: "dark",
    });
    const byId = Object.fromEntries(statuses.map((c) => [c.id, c]));
    expect(byId["sidecar-llm"].status).toBe("available");
    expect(byId["sidecar-connectors"].status).toBe("available");
    expect(byId["sidecar-mcp"].status).toBe("available");
    expect(byId["sidecar-import"].status).toBe("available");
    localStorage.removeItem("studio.token");
  });

  it("returns all eight capability ids", async () => {
    const statuses = await capabilityRegistry.statuses({
      base_url: "http://localhost:8001/v1",
      api_key: "local",
      model_name: "local-tools-model",
      mcp_url: "http://localhost:8000/mcp",
      theme: "dark",
    });
    expect(
      statuses.map((c) => c.id),
    ).toEqual([
      "local-data",
      "local-memory",
      "deterministic-assistant",
      "browser-model",
      "endpoint-model",
      "sidecar-llm",
      "sidecar-connectors",
      "sidecar-mcp",
      "sidecar-import",
    ]);
    expect(statuses).toHaveLength(9);
  });
});
