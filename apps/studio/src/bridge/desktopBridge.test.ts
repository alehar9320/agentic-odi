import { afterEach, describe, expect, it } from "vitest";

import { SIDECAR_ORIGIN, apiUrl, isTauri, resolveApiBase } from "./desktopBridge";

afterEach(() => {
  delete (window as unknown as { __TAURI_INTERNALS__?: unknown }).__TAURI_INTERNALS__;
});

describe("isTauri", () => {
  it("detects the Tauri runtime marker", () => {
    expect(isTauri()).toBe(false);
    (window as unknown as { __TAURI_INTERNALS__?: unknown }).__TAURI_INTERNALS__ = {};
    expect(isTauri()).toBe(true);
  });
});

describe("resolveApiBase", () => {
  it("uses a relative base in the browser and an absolute sidecar origin in Tauri", () => {
    expect(resolveApiBase(false)).toBe("");
    expect(resolveApiBase(true)).toBe(SIDECAR_ORIGIN);
  });
});

describe("apiUrl", () => {
  it("uses the vite proxy / served origin in the browser", () => {
    expect(apiUrl("/api/config")).toBe("/api/config");
  });

  it("targets the sidecar directly inside Tauri", () => {
    (window as unknown as { __TAURI_INTERNALS__?: unknown }).__TAURI_INTERNALS__ = {};
    expect(apiUrl("/api/config")).toBe(`${SIDECAR_ORIGIN}/api/config`);
  });
});
