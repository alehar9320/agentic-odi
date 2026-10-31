import { describe, expect, it } from "vitest";

import { isEndpointConfigured, isEndpointConfiguredForSettings } from "./modelEndpoint";

function endpoint(overrides: Partial<{ base_url: string; api_key: string; model: string }> = {}) {
  return {
    base_url: "https://api.openai.com/v1",
    api_key: "sk-test",
    model: "gpt-4o-mini",
    ...overrides,
  };
}

describe("model endpoint configuration", () => {
  it("counts a public endpoint with a key", () => {
    expect(isEndpointConfigured(endpoint())).toBe(true);
  });

  it("refuses a public endpoint with no key", () => {
    expect(isEndpointConfigured(endpoint({ api_key: "" }))).toBe(false);
  });

  it.each([
    ["loopback", "http://127.0.0.1:11434/v1"],
    ["localhost by name", "http://localhost:1234/v1"],
    ["a .localhost host", "http://lmstudio.localhost:1234/v1"],
    ["bracketed IPv6 loopback", "http://[::1]:11434/v1"],
    ["10/8", "http://10.0.4.9:11434/v1"],
    ["172.16/12", "http://172.20.0.3:11434/v1"],
    ["192.168/16", "http://192.168.1.40:11434/v1"],
  ])("accepts a keyless %s server", (_label, base_url) => {
    expect(isEndpointConfigured(endpoint({ base_url, api_key: "" }))).toBe(true);
  });

  it.each([
    ["a host outside the private ranges", "http://192.169.1.40:11434/v1"],
    ["the upper half of 172/8", "http://172.32.0.3:11434/v1"],
    ["a public hostname", "https://model.example.com/v1"],
  ])("still requires a key for %s", (_label, base_url) => {
    expect(isEndpointConfigured(endpoint({ base_url, api_key: "" }))).toBe(false);
  });

  it("treats the sidecar proxy default as no endpoint of its own", () => {
    expect(isEndpointConfigured(endpoint({ base_url: "http://localhost:8001/v1", api_key: "" }))).toBe(
      false,
    );
    expect(
      isEndpointConfigured(endpoint({ base_url: "http://localhost:8001/v1/", api_key: "" })),
    ).toBe(false);
  });

  it("needs both an address and a model name", () => {
    expect(isEndpointConfigured(endpoint({ base_url: "" }))).toBe(false);
    expect(isEndpointConfigured(endpoint({ model: "" }))).toBe(false);
    expect(isEndpointConfigured(endpoint({ base_url: "not a url", api_key: "" }))).toBe(false);
  });

  it("answers the same question for stored settings", () => {
    expect(
      isEndpointConfiguredForSettings({
        base_url: "http://127.0.0.1:11434/v1",
        api_key: "",
        model_name: "qwen3",
      }),
    ).toBe(true);
  });
});
