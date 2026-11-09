import { describe, expect, it, vi, afterEach } from "vitest";

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
});
