import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { capabilityRegistry } from "./registry";

const CONFIG = {
  base_url: "http://localhost:8001/v1",
  api_key: "local",
  model_name: "local-tools-model",
  mcp_url: "http://localhost:8000/mcp",
  theme: "dark" as const,
};

function capabilitiesResponse(items: Array<{ id: string; available: boolean; reason?: string }>) {
  return new Response(JSON.stringify({ capabilities: items }), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

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
    const statuses = await capabilityRegistry.statuses(CONFIG);

    const byId = Object.fromEntries(statuses.map((c) => [c.id, c]));
    expect(byId["local-data"].status).toBe("available");
    expect(byId["local-memory"].status).toBe("available");
    expect(byId["deterministic-assistant"].status).toBe("available");
  });

  it("reports endpoint-model as unavailable for default local config", async () => {
    const statuses = await capabilityRegistry.statuses(CONFIG);
    const byId = Object.fromEntries(statuses.map((c) => [c.id, c]));
    expect(byId["endpoint-model"].status).toBe("unavailable");
  });

  it("reports endpoint-model as available for a configured external endpoint", async () => {
    const statuses = await capabilityRegistry.statuses({
      ...CONFIG,
      base_url: "https://api.example.com/v1",
      api_key: "sk-test",
      model_name: "gpt-4o",
    });
    const byId = Object.fromEntries(statuses.map((c) => [c.id, c]));
    expect(byId["endpoint-model"].status).toBe("available");
  });

  it("reports sidecar capabilities as unavailable when the manifest is unreachable", async () => {
    const statuses = await capabilityRegistry.statuses(CONFIG);
    const byId = Object.fromEntries(statuses.map((c) => [c.id, c]));
    expect(byId["sidecar-llm"].status).toBe("unavailable");
    expect(byId["sidecar-connectors"].status).toBe("unavailable");
    expect(byId["sidecar-mcp"].status).toBe("unavailable");
    expect(byId["sidecar-import"].status).toBe("unavailable");
    expect(byId["sidecar-llm"].reason).toContain("not reachable");
  });

  it("maps every sidecar row from one capabilities manifest fetch", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      if (String(input).includes("/api/capabilities")) {
        return capabilitiesResponse([
          { id: "sidecar-llm", available: true },
          { id: "sidecar-connectors", available: true },
          { id: "sidecar-mcp", available: false, reason: "MCP is switched off." },
          { id: "sidecar-import", available: true },
        ]);
      }
      return new Response("", { status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);

    const statuses = await capabilityRegistry.statuses(CONFIG);
    const byId = Object.fromEntries(statuses.map((c) => [c.id, c]));
    expect(byId["sidecar-llm"].status).toBe("available");
    expect(byId["sidecar-connectors"].status).toBe("available");
    expect(byId["sidecar-mcp"].status).toBe("unavailable");
    expect(byId["sidecar-mcp"].reason).toBe("MCP is switched off.");
    expect(byId["sidecar-import"].status).toBe("available");

    const manifestCalls = fetchMock.mock.calls.filter(([input]) =>
      String(input).includes("/api/capabilities"),
    );
    expect(manifestCalls).toHaveLength(1);
  });

  it("never probes the retired per-route sidecar endpoints", async () => {
    const fetchMock = vi.fn<typeof fetch>(async () => new Response("", { status: 404 }));
    vi.stubGlobal("fetch", fetchMock);

    await capabilityRegistry.statuses(CONFIG);

    const urls = fetchMock.mock.calls.map(([input]) => String(input));
    expect(urls.some((url) => url.includes("/api/health/mcp"))).toBe(false);
    expect(urls.some((url) => url.includes("/api/connectors"))).toBe(false);
  });

  it("reports a downloadable browser model as downloadable, not available", async () => {
    vi.stubGlobal("LanguageModel", { availability: () => "downloadable" });
    const statuses = await capabilityRegistry.statuses(CONFIG);
    const byId = Object.fromEntries(statuses.map((c) => [c.id, c]));
    expect(byId["browser-model"].status).toBe("downloadable");
    expect(byId["browser-model"].reason).toBeTruthy();
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
        if (String(input).includes("/api/capabilities")) {
          return capabilitiesResponse([
            { id: "sidecar-llm", available: true },
            { id: "sidecar-import", available: true },
          ]);
        }
        return new Response("", { status: 404 });
      }),
    );
    const statuses = await capabilityRegistry.statuses(CONFIG);
    const byId = Object.fromEntries(statuses.map((c) => [c.id, c]));
    expect(byId["sidecar-llm"].status).toBe("available");
    expect(byId["sidecar-import"].status).toBe("available");
    localStorage.removeItem("studio.token");
  });

  it("returns all nine capability ids in catalog order", async () => {
    const statuses = await capabilityRegistry.statuses(CONFIG);
    expect(statuses.map((c) => c.id)).toEqual([
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
      ...CONFIG,
      base_url: "http://127.0.0.1:11434/v1",
      api_key: "",
      model_name: "qwen3:8b",
    });
    const byId = Object.fromEntries(statuses.map((c) => [c.id, c]));
    expect(byId["endpoint-model"].status).toBe("unavailable");
    expect(byId["endpoint-model"].reason).toContain("on your machine");
    expect(byId["endpoint-model"].reason).toContain("desktop app");
  });

  it("reports endpoint-model as available for a private endpoint on a device page", async () => {
    setHostname("localhost");
    const statuses = await capabilityRegistry.statuses({
      ...CONFIG,
      base_url: "http://127.0.0.1:11434/v1",
      api_key: "",
      model_name: "qwen3:8b",
    });
    const byId = Object.fromEntries(statuses.map((c) => [c.id, c]));
    expect(byId["endpoint-model"].status).toBe("available");
  });

  it("reports endpoint-model as available for a public endpoint on a hosted page", async () => {
    setHostname("studio.example.com");
    const statuses = await capabilityRegistry.statuses({
      ...CONFIG,
      base_url: "https://api.example.com/v1",
      api_key: "sk-test",
      model_name: "gpt-4o",
    });
    const byId = Object.fromEntries(statuses.map((c) => [c.id, c]));
    expect(byId["endpoint-model"].status).toBe("available");
  });
});
