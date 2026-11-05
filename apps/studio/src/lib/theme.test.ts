import { renderHook, act } from "@testing-library/react";
import { describe, expect, it, vi, afterEach } from "vitest";

import { LIGHT_QUERY, resolveTheme, storedPreference, useSystemTheme } from "./theme";
import { stubLiveMatchMedia } from "../test/matchMedia";
import type { StudioThemePreference } from "../types";

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

  it("follows the operating system when the reader asked it to", () => {
    expect(resolveTheme("system", true)).toBe("light");
    expect(resolveTheme("system", false)).toBe("dark");
  });

  it("keeps a stored palette over a system that disagrees", () => {
    expect(resolveTheme("light", false)).toBe("light");
    expect(resolveTheme("dark", true)).toBe("dark");
  });

  it("treats a value that is not a theme as no choice at all", () => {
    expect(resolveTheme("neon" as StudioThemePreference, true)).toBe("light");
    expect(resolveTheme("neon" as StudioThemePreference, false)).toBe("dark");
  });

  it("reads an untouched setting and an explicit system choice as the same request", () => {
    expect(resolveTheme(undefined, true)).toBe(resolveTheme("system", true));
    expect(resolveTheme(undefined, false)).toBe(resolveTheme("system", false));
  });
});

describe("storedPreference", () => {
  it("reads a choice that was never made as following the system", () => {
    expect(storedPreference(undefined)).toBe("system");
  });

  it("leaves a choice that was made exactly as it was stored", () => {
    expect(storedPreference("light")).toBe("light");
    expect(storedPreference("dark")).toBe("dark");
    expect(storedPreference("system")).toBe("system");
  });
});

describe("useSystemTheme", () => {
  const original = window.matchMedia;

  afterEach(() => {
    Object.defineProperty(window, "matchMedia", {
      configurable: true,
      writable: true,
      value: original,
    });
  });

  it("reports the operating system and moves when it moves", () => {
    const media = stubLiveMatchMedia(true);
    const { result, unmount } = renderHook(() => useSystemTheme());

    expect(result.current).toBe("light");

    act(() => media.set(false));
    act(() => media.fire());
    expect(result.current).toBe("dark");

    unmount();
    expect(media.subscribed).toBe(0);
  });

  it("asks the same question the bootstrap in index.html asks", () => {
    const media = stubLiveMatchMedia(false);
    renderHook(() => useSystemTheme());

    expect(media.subscribed).toBe(1);
    expect(media.asked).toContain(LIGHT_QUERY);
  });

  it("answers dark and subscribes to nothing when the browser cannot answer", () => {
    Object.defineProperty(window, "matchMedia", {
      configurable: true,
      writable: true,
      value: undefined,
    });
    const { result, rerender } = renderHook(() => useSystemTheme());

    expect(result.current).toBe("dark");
    rerender();
    expect(result.current).toBe("dark");
  });
});
