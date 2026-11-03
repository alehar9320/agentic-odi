import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { capabilityRegistry } from "./registry";

const settings = {
  base_url: "http://localhost:8001/v1",
  api_key: "local",
  model_name: "local-tools-model",
  mcp_url: "http://localhost:8000/mcp",
  theme: "dark",
} as const;

const stubbedKeys = new Map<string, PropertyDescriptor | undefined>();

function stubNavigator(key: string, value: unknown): void {
  if (!stubbedKeys.has(key)) {
    stubbedKeys.set(key, Object.getOwnPropertyDescriptor(navigator, key));
  }
  Object.defineProperty(navigator, key, { value, configurable: true });
}

function webgpuStub(f16: boolean): void {
  stubNavigator("gpu", {
    requestAdapter: async () => ({ features: { has: (name: string) => f16 && name === "shader-f16" } }),
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
  for (const [key, descriptor] of stubbedKeys) {
    if (descriptor) {
      Object.defineProperty(navigator, key, descriptor);
    } else {
      delete (navigator as unknown as Record<string, unknown>)[key];
    }
  }
  stubbedKeys.clear();
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

  it("explains why the browser model is out of reach without WebGPU", async () => {
    const statuses = await capabilityRegistry.statuses(settings);
    const byId = Object.fromEntries(statuses.map((c) => [c.id, c]));
    expect(byId["browser-model"].status).toBe("unavailable");
    expect(byId["browser-model"].reason).toMatch(/browser doesn't support GPU/i);
  });

  it("reports the browser model available on a WebGPU device with f16", async () => {
    webgpuStub(true);
    stubNavigator("deviceMemory", 8);
    const statuses = await capabilityRegistry.statuses(settings);
    const byId = Object.fromEntries(statuses.map((c) => [c.id, c]));
    expect(byId["browser-model"].status).toBe("available");
    expect(byId["browser-model"].reason).toBeUndefined();
  });

  it("says the 16-bit format is missing when the GPU lacks shader-f16", async () => {
    webgpuStub(false);
    stubNavigator("deviceMemory", 8);
    const statuses = await capabilityRegistry.statuses(settings);
    const byId = Object.fromEntries(statuses.map((c) => [c.id, c]));
    expect(byId["browser-model"].status).toBe("unavailable");
    expect(byId["browser-model"].reason).toMatch(/16-bit/i);
  });
});
