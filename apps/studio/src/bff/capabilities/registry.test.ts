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

  it("reports endpoint-model as unavailable for default local config", async () => {
    const statuses = await capabilityRegistry.statuses({
      base_url: "http://localhost:8001/v1",
      api_key: "local",
      model_name: "local-tools-model",
      mcp_url: "http://localhost:8000/mcp",
      theme: "dark",
    });
    const byId = Object.fromEntries(statuses.map((c) => [c.id, c]));
    expect(byId["endpoint-model"].status).toBe("unavailable");
  });

  it("reports endpoint-model as available for a configured external endpoint", async () => {
    const statuses = await capabilityRegistry.statuses({
      base_url: "https://api.example.com/v1",
      api_key: "sk-test",
      model_name: "gpt-4o",
      mcp_url: "http://localhost:8000/mcp",
      theme: "dark",
    });
    const byId = Object.fromEntries(statuses.map((c) => [c.id, c]));
    expect(byId["endpoint-model"].status).toBe("available");
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
        if (url.includes("/api/connectors") || url.includes("/api/health/mcp")) {
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
        if (url.includes("/api/connectors") || url.includes("/api/health/mcp")) {
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

describe("browser-model status", () => {
  const settings = {
    base_url: "http://localhost:8001/v1",
    api_key: "local",
    model_name: "local-tools-model",
    mcp_url: "http://localhost:8000/mcp",
    theme: "dark" as const,
  };

  it("sees a model under either spelling, so the status matches the provider", async () => {
    vi.stubGlobal("LanguageModel", { availability: vi.fn(), create: vi.fn() });
    let byId = Object.fromEntries(
      (await capabilityRegistry.statuses(settings)).map((c) => [c.id, c]),
    );
    expect(byId["browser-model"].status).toBe("available");

    vi.unstubAllGlobals();
    vi.stubGlobal("ai", { languageModel: { availability: vi.fn(), create: vi.fn() } });
    byId = Object.fromEntries(
      (await capabilityRegistry.statuses(settings)).map((c) => [c.id, c]),
    );
    expect(byId["browser-model"].status).toBe("available");
  });

  it("reports no model when the browser has none", async () => {
    const byId = Object.fromEntries(
      (await capabilityRegistry.statuses(settings)).map((c) => [c.id, c]),
    );
    expect(byId["browser-model"].status).toBe("unavailable");
  });
});

describe("endpoint-model reachability", () => {
  let originalLocation: Location;

  const setHostname = (value: string) => {
    originalLocation = window.location;
    Object.defineProperty(window, "location", {
      configurable: true,
      get() {
        return new Proxy(originalLocation, {
          get(target, prop) {
            if (prop === "hostname") return value;
            return Reflect.get(target, prop);
          },
        });
      },
    });
  };

  afterEach(() => {
    Object.defineProperty(window, "location", {
      value: originalLocation,
      configurable: true,
    });
  });

  it("reports endpoint-model as device-only for a private endpoint on a hosted page", async () => {
    setHostname("studio.example.com");
    const statuses = await capabilityRegistry.statuses({
      base_url: "http://127.0.0.1:11434/v1",
      api_key: "",
      model_name: "qwen3:8b",
      mcp_url: "http://localhost:8000/mcp",
      theme: "dark",
    });
    const byId = Object.fromEntries(statuses.map((c) => [c.id, c]));
    expect(byId["endpoint-model"].status).toBe("unavailable");
    expect(byId["endpoint-model"].reason).toContain("on your machine");
    expect(byId["endpoint-model"].reason).toContain("desktop app");
  });

  it("reports endpoint-model as available for a private endpoint on a device page", async () => {
    setHostname("localhost");
    const statuses = await capabilityRegistry.statuses({
      base_url: "http://127.0.0.1:11434/v1",
      api_key: "",
      model_name: "qwen3:8b",
      mcp_url: "http://localhost:8000/mcp",
      theme: "dark",
    });
    const byId = Object.fromEntries(statuses.map((c) => [c.id, c]));
    expect(byId["endpoint-model"].status).toBe("available");
  });

  it("reports endpoint-model as available for a public endpoint on a hosted page", async () => {
    setHostname("studio.example.com");
    const statuses = await capabilityRegistry.statuses({
      base_url: "https://api.example.com/v1",
      api_key: "sk-test",
      model_name: "gpt-4o",
      mcp_url: "http://localhost:8000/mcp",
      theme: "dark",
    });
    const byId = Object.fromEntries(statuses.map((c) => [c.id, c]));
    expect(byId["endpoint-model"].status).toBe("available");
  });
});
