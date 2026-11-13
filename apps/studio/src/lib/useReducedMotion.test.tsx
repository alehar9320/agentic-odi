import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { useReducedMotion } from "./useReducedMotion";

/**
 * The preference is live, not read once at mount: toggling the OS setting has
 * to reach JS-driven motion without a reload.
 */
describe("useReducedMotion", () => {
  const original = window.matchMedia;

  afterEach(() => {
    Object.defineProperty(window, "matchMedia", {
      configurable: true,
      writable: true,
      value: original,
    });
  });

  function stubMatchMedia(initial: boolean) {
    const listeners = new Set<() => void>();
    let matches = initial;
    Object.defineProperty(window, "matchMedia", {
      configurable: true,
      writable: true,
      value: (query: string) => ({
        get matches() {
          return query.includes("prefers-reduced-motion") ? matches : false;
        },
        media: query,
        onchange: null,
        addEventListener: (_: string, listener: () => void) => listeners.add(listener),
        removeEventListener: (_: string, listener: () => void) => listeners.delete(listener),
        addListener: () => {},
        removeListener: () => {},
        dispatchEvent: () => false,
      }),
    });
    return {
      toggle(next: boolean) {
        matches = next;
        for (const listener of listeners) {
          listener();
        }
      },
    };
  }

  it("reports the current preference", () => {
    stubMatchMedia(true);
    const { result } = renderHook(() => useReducedMotion());
    expect(result.current).toBe(true);
  });

  it("follows a change without a reload", () => {
    const media = stubMatchMedia(false);
    const { result } = renderHook(() => useReducedMotion());
    expect(result.current).toBe(false);

    act(() => media.toggle(true));
    expect(result.current).toBe(true);

    act(() => media.toggle(false));
    expect(result.current).toBe(false);
  });

  it("defaults to no preference when matchMedia is unavailable", () => {
    Object.defineProperty(window, "matchMedia", {
      configurable: true,
      writable: true,
      value: undefined,
    });
    const { result } = renderHook(() => useReducedMotion());
    expect(result.current).toBe(false);
  });
});
