import { beforeEach, describe, expect, it } from "vitest";

import {
  FEATURE_FLAGS,
  clearFeatureOverride,
  isFeatureEnabled,
  parseFlagValue,
  resolveFlag,
  setFeatureOverride,
} from "./flags";

describe("parseFlagValue", () => {
  it.each([
    ["1", true],
    ["true", true],
    ["ON", true],
    [" yes ", true],
    ["0", false],
    ["false", false],
    ["Off", false],
    ["nope", null],
    ["", null],
    [null, null],
    [undefined, null],
  ])("parses %j as %j", (raw, expected) => {
    expect(parseFlagValue(raw as string | null | undefined)).toBe(expected);
  });
});

describe("first-run wizard flag", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("is on by default", () => {
    expect(resolveFlag("firstRunWizard", {}).source).toBe("default");
    expect(isFeatureEnabled("firstRunWizard", {})).toBe(true);
  });

  it("reads a build-time env override", () => {
    expect(resolveFlag("firstRunWizard", { env: "off" })).toEqual({
      enabled: false,
      source: "env",
      raw: "off",
    });
  });

  it("lets a stored override beat the env", () => {
    expect(resolveFlag("firstRunWizard", { env: "off", stored: "on" })).toEqual({
      enabled: true,
      source: "storage",
      raw: "on",
    });
  });

  it("lets a query override beat storage", () => {
    expect(resolveFlag("firstRunWizard", { env: "off", stored: "off", query: "on" })).toEqual({
      enabled: true,
      source: "query",
      raw: "on",
    });
  });

  it("falls through when a higher-precedence value is unrecognized", () => {
    const resolved = resolveFlag("firstRunWizard", {
      query: "maybe",
      stored: "off",
      env: "on",
    });
    expect(resolved.enabled).toBe(false);
    expect(resolved.source).toBe("storage");
  });

  it("writes and clears a local override", () => {
    setFeatureOverride("firstRunWizard", false);
    expect(window.localStorage.getItem("studio.flags.firstRunWizard")).toBe("off");
    expect(
      resolveFlag("firstRunWizard", {
        stored: window.localStorage.getItem("studio.flags.firstRunWizard"),
      }).enabled,
    ).toBe(false);

    clearFeatureOverride("firstRunWizard");
    expect(window.localStorage.getItem("studio.flags.firstRunWizard")).toBeNull();
  });

  it("declares an env variable for every flag", () => {
    for (const definition of Object.values(FEATURE_FLAGS)) {
      expect(definition.envVar).toMatch(/^VITE_/);
      expect(definition.description.length).toBeGreaterThan(0);
    }
  });
});
