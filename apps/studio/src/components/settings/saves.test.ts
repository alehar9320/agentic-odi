import { describe, expect, it } from "vitest";

import { summarizeSaves, type FieldSaveStatus } from "./saves";
import { validateBaseUrl, validateMcpUrl, validateModelName } from "./validation";

describe("settings validation", () => {
  it("accepts an http or https address", () => {
    expect(validateBaseUrl("http://localhost:8001/v1")).toBeNull();
    expect(validateMcpUrl("https://bridge.example.com/mcp")).toBeNull();
  });

  it("refuses anything that is not a full URL", () => {
    expect(validateBaseUrl("not a url")).toMatch(/full URL/i);
    expect(validateBaseUrl("")).toMatch(/full URL/i);
    expect(validateMcpUrl("ftp://nope")).toMatch(/http/i);
  });

  it("requires a model name", () => {
    expect(validateModelName("qwen3-8b")).toBeNull();
    expect(validateModelName("   ")).toMatch(/model name/i);
  });
});

describe("summarizeSaves", () => {
  const saved: FieldSaveStatus = { kind: "saved" };
  const idle: FieldSaveStatus = { kind: "idle" };
  const failed: FieldSaveStatus = { kind: "error", reason: "bad url" };

  it("stays idle until something is attempted", () => {
    expect(summarizeSaves([idle, idle])).toEqual({ kind: "idle" });
    expect(summarizeSaves([])).toEqual({ kind: "idle" });
  });

  it("reports saved once any field landed", () => {
    expect(summarizeSaves([idle, saved])).toEqual({ kind: "saved" });
  });

  it("never claims saved while a field is refused", () => {
    expect(summarizeSaves([saved, failed])).toEqual(failed);
  });
});
