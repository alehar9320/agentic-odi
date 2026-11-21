import { describe, expect, it } from "vitest";

import {
  clearLegacyApiKey,
  EMPTY_CONFIG,
  readLegacyApiKey,
  SETTINGS_KEY,
} from "./SettingsContext";

const STORED = {
  base_url: "http://localhost:8001/v1",
  api_key: "sk-DO-NOT-LEAK",
  model_name: "local-tools-model",
  mcp_url: "http://localhost:8000/mcp",
};

describe("settings never keep the model key in the browser", () => {
  it("reads a legacy key once so it can be handed to the sidecar", () => {
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(STORED));

    expect(readLegacyApiKey()).toBe("sk-DO-NOT-LEAK");
  });

  it("does not treat the shipped default as a secret to migrate", () => {
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(EMPTY_CONFIG));

    expect(readLegacyApiKey()).toBeNull();
  });

  it("removes the key from the stored settings and leaves the rest", () => {
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(STORED));

    clearLegacyApiKey();

    const stored = JSON.parse(localStorage.getItem(SETTINGS_KEY) ?? "{}");
    // The field is dropped, not blanked: nothing a script reads holds a key.
    expect("api_key" in stored).toBe(false);
    expect(localStorage.getItem(SETTINGS_KEY)).not.toContain("sk-DO-NOT-LEAK");
    expect(stored.model_name).toBe("local-tools-model");
  });

  it("is a no-op when nothing is stored, and idempotent when something is", () => {
    expect(() => clearLegacyApiKey()).not.toThrow();

    localStorage.setItem(SETTINGS_KEY, JSON.stringify(STORED));
    clearLegacyApiKey();
    const once = localStorage.getItem(SETTINGS_KEY);
    clearLegacyApiKey();
    expect(localStorage.getItem(SETTINGS_KEY)).toBe(once);
  });
});
