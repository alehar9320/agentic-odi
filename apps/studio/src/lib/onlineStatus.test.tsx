import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { isOnline, useOnlineStatus } from "./onlineStatus";

/** jsdom's `navigator.onLine` is a plain property; redefine it per test and put
 * the original back afterwards. */
const original = Object.getOwnPropertyDescriptor(window.navigator, "onLine");

function setOnLine(value: boolean) {
  Object.defineProperty(window.navigator, "onLine", {
    value,
    configurable: true,
  });
}

afterEach(() => {
  if (original) {
    Object.defineProperty(window.navigator, "onLine", original);
  }
});

describe("isOnline", () => {
  it("reads the browser's own connectivity flag", () => {
    setOnLine(true);
    expect(isOnline()).toBe(true);
    setOnLine(false);
    expect(isOnline()).toBe(false);
  });
});

describe("useOnlineStatus", () => {
  it("starts from the current state", () => {
    setOnLine(false);
    const { result } = renderHook(() => useOnlineStatus());
    expect(result.current).toBe(false);
  });

  it("follows the browser offline and back online", () => {
    setOnLine(true);
    const { result } = renderHook(() => useOnlineStatus());
    expect(result.current).toBe(true);

    act(() => {
      setOnLine(false);
      window.dispatchEvent(new Event("offline"));
    });
    expect(result.current).toBe(false);

    act(() => {
      setOnLine(true);
      window.dispatchEvent(new Event("online"));
    });
    expect(result.current).toBe(true);
  });

  it("stops listening once the component unmounts", () => {
    setOnLine(true);
    const { result, unmount } = renderHook(() => useOnlineStatus());
    unmount();

    act(() => {
      setOnLine(false);
      window.dispatchEvent(new Event("offline"));
    });

    // The last render still reads true; nothing threw after unmount.
    expect(result.current).toBe(true);
  });
});
