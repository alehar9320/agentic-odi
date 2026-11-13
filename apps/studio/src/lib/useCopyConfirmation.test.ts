import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { COPY_CONFIRMATION_MS, useCopyConfirmation } from "./useCopyConfirmation";

describe("useCopyConfirmation", () => {
  let writeText: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    writeText = vi.fn(async () => {});
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText },
      configurable: true,
    });
  });

  it("confirms for 1600ms and then reads Copy again", async () => {
    expect(COPY_CONFIRMATION_MS).toBe(1600);
    vi.useFakeTimers();
    const { result } = renderHook(() => useCopyConfirmation());

    await act(async () => {
      await result.current.copy("hello");
    });
    expect(writeText).toHaveBeenCalledWith("hello");
    expect(result.current.copied).toBe(true);

    act(() => {
      vi.advanceTimersByTime(COPY_CONFIRMATION_MS);
    });
    expect(result.current.copied).toBe(false);
  });

  it("re-triggers on a second copy instead of stacking timers", async () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => useCopyConfirmation());

    await act(async () => {
      await result.current.copy("one");
    });
    act(() => {
      vi.advanceTimersByTime(1000);
    });
    await act(async () => {
      await result.current.copy("two");
    });

    // The first timer would have fired at 1600ms; the second copy restarts it.
    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(result.current.copied).toBe(true);
    act(() => {
      vi.advanceTimersByTime(600);
    });
    expect(result.current.copied).toBe(false);
  });

  it("stays quiet when the clipboard refuses", async () => {
    writeText.mockRejectedValue(new Error("denied"));
    const { result } = renderHook(() => useCopyConfirmation());

    let ok = true;
    await act(async () => {
      ok = await result.current.copy("nope");
    });
    expect(ok).toBe(false);
    expect(result.current.copied).toBe(false);
  });
});
