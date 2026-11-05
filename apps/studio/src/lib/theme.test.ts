import { describe, expect, it, vi, afterEach } from "vitest";

import type { StudioTheme } from "../types";
import { resolveTheme } from "./theme";

function stubMatchMedia(matches: boolean): void {
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    writable: true,
    value: (query: string) => ({
      matches: query.includes("prefers-color-scheme: light") ? matches : false,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(() => false),
    }),
  });
}

describe("resolveTheme", () => {
  const original = window.matchMedia;

  afterEach(() => {
    Object.defineProperty(window, "matchMedia", {
      configurable: true,
      writable: true,
      value: original,
    });
  });

  it("uses the stored choice even when the system disagrees", () => {
    stubMatchMedia(false);
    expect(resolveTheme("light")).toBe("light");
    stubMatchMedia(true);
    expect(resolveTheme("dark")).toBe("dark");
  });

  it("follows the media query when nothing is stored", () => {
    stubMatchMedia(true);
    expect(resolveTheme(undefined)).toBe("light");
    stubMatchMedia(false);
    expect(resolveTheme(undefined)).toBe("dark");
  });

  it("falls back to dark when the browser cannot answer the media query", () => {
    Object.defineProperty(window, "matchMedia", {
      configurable: true,
      writable: true,
      value: undefined,
    });
    expect(resolveTheme(undefined)).toBe("dark");
  });

  it("treats a stored system choice as the operating system's answer", () => {
    stubMatchMedia(true);
    expect(resolveTheme("system")).toBe("light");
    stubMatchMedia(false);
    expect(resolveTheme("system")).toBe("dark");
  });

  it("uses the operating system's answer the caller is holding, not a fresh read", () => {
    // A component that subscribed to the media query has a current answer in
    // hand; reading `matchMedia` again here would be a second, uncoupled source
    // of truth that can disagree with the value that triggered the render.
    stubMatchMedia(true);
    expect(resolveTheme("system", false)).toBe("dark");
    expect(resolveTheme(undefined, false)).toBe("dark");
    expect(resolveTheme("light", false)).toBe("light");
  });

  it("follows the operating system when the stored value is not a theme", () => {
    // Settings are read straight out of `localStorage`, so anything can be in
    // there. A value the app never offered must not decide the palette.
    stubMatchMedia(true);
    expect(resolveTheme("midnight" as StudioTheme, false)).toBe("dark");
    expect(resolveTheme("midnight" as StudioTheme, true)).toBe("light");
  });
});
