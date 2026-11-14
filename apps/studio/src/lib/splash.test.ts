import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const invoke = vi.fn();
vi.mock("@tauri-apps/api/core", () => ({
  invoke: (...args: unknown[]) => invoke(...args),
}));

import { SPLASH_ACK_TIMEOUT_MS, signalSplashComplete } from "./splash";

function setDesktop(on: boolean): void {
  const desktop = window as unknown as { __TAURI_INTERNALS__?: unknown };
  if (on) {
    desktop.__TAURI_INTERNALS__ = {};
    return;
  }
  delete desktop.__TAURI_INTERNALS__;
}

describe("signalSplashComplete", () => {
  beforeEach(() => {
    invoke.mockReset();
    setDesktop(false);
  });

  afterEach(() => {
    setDesktop(false);
    vi.useRealTimers();
  });

  it("does nothing in the browser, which keeps its own boot shell", async () => {
    await signalSplashComplete();
    expect(invoke).not.toHaveBeenCalled();
  });

  it("reports the commit to the desktop shell", async () => {
    setDesktop(true);
    invoke.mockResolvedValue(undefined);

    await signalSplashComplete();

    expect(invoke).toHaveBeenCalledWith("set_complete");
  });

  it("never rejects when the shell is unreachable", async () => {
    setDesktop(true);
    invoke.mockRejectedValue(new Error("no such command"));

    await expect(signalSplashComplete()).resolves.toBeUndefined();
  });

  it("gives up after the ack timeout instead of hanging the boot", async () => {
    setDesktop(true);
    invoke.mockReturnValue(new Promise(() => {}));
    vi.useFakeTimers();

    const reported = signalSplashComplete();
    await vi.advanceTimersByTimeAsync(SPLASH_ACK_TIMEOUT_MS);

    await expect(reported).resolves.toBeUndefined();
  });
});
