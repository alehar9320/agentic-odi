import { describe, expect, it, vi } from "vitest";

import { StudioApiError } from "../api/studioApi";
import type { StudioError } from "../types";
import {
  BREAKER_FAILURE_THRESHOLD,
  BREAKER_OPEN_MS,
  classifyProbeError,
  createProbeBreaker,
  formatRetryCountdown,
} from "./probeBreaker";

/** A controllable clock, so the breaker's window is tested without waiting. */
function clock(start = 0) {
  let value = start;
  return {
    now: () => value,
    advance: (ms: number) => {
      value += ms;
    },
  };
}

function appError(code: string, status = 400): StudioApiError {
  const error: StudioError = {
    code,
    message: code,
    retryable: false,
  };
  return new StudioApiError(error, status, true);
}

describe("classifyProbeError", () => {
  it("calls a network failure transport", () => {
    expect(classifyProbeError(new TypeError("fetch failed"))).toBe("transport");
  });

  it("calls a proxy 502 without a sidecar body transport", () => {
    expect(classifyProbeError(new StudioApiError({ code: "mcp_unreachable", message: "x", retryable: true }, 502, false))).toBe(
      "transport",
    );
  });

  it("treats a rejected key as degraded", () => {
    expect(classifyProbeError(appError("unauthorized", 401))).toBe("degraded");
  });

  it("treats a missing model as degraded", () => {
    expect(classifyProbeError(appError("not_found", 404))).toBe("degraded");
  });

  it("treats a sidecar 5xx as retryable", () => {
    expect(classifyProbeError(appError("internal", 500))).toBe("retryable");
  });
});

describe("createProbeBreaker", () => {
  it("runs one probe at a time and lets a second caller join it", async () => {
    const breaker = createProbeBreaker();
    let resolve!: (value: { outcome: "success"; value: string }) => void;
    const probe = vi.fn(
      () =>
        new Promise<{ outcome: "success"; value: string }>((r) => {
          resolve = r;
        }),
    );

    const first = breaker.run(probe);
    const second = breaker.run(probe);
    expect(probe).toHaveBeenCalledTimes(1);

    resolve({ outcome: "success", value: "the report" });
    await expect(first).resolves.toEqual({ outcome: "success", value: "the report" });
    // The joined caller sees the same value, not a second measurement.
    await expect(second).resolves.toEqual({ outcome: "success", value: "the report" });
    expect(probe).toHaveBeenCalledTimes(1);
  });

  it("does not start a second probe after the first settles", async () => {
    const breaker = createProbeBreaker();
    const probe = vi.fn(async () => ({ outcome: "success" as const, value: null }));

    await breaker.run(probe);
    await breaker.run(probe);
    expect(probe).toHaveBeenCalledTimes(2);
  });

  it("opens after three consecutive retryable failures", async () => {
    const time = clock();
    const breaker = createProbeBreaker({ now: time.now });
    const probe = vi.fn(async () => ({ outcome: "transport" as const, value: null }));

    await breaker.run(probe);
    await breaker.run(probe);
    await breaker.run(probe);

    expect(breaker.state()).toBe("open");
    expect(breaker.failures()).toBe(BREAKER_FAILURE_THRESHOLD);
  });

  it("refuses to run a probe while open", async () => {
    const time = clock();
    const breaker = createProbeBreaker({ now: time.now });
    const failing = vi.fn(async () => ({ outcome: "transport" as const, value: null }));
    for (let i = 0; i < BREAKER_FAILURE_THRESHOLD; i += 1) {
      await breaker.run(failing);
    }

    const probe = vi.fn(async () => ({ outcome: "success" as const, value: null }));
    await expect(breaker.run(probe)).resolves.toBeNull();
    expect(probe).not.toHaveBeenCalled();
    expect(breaker.allows()).toBe(false);
  });

  it("allows one half-open probe after the window, and closes on success", async () => {
    const time = clock();
    const breaker = createProbeBreaker({ now: time.now });
    const failing = vi.fn(async () => ({ outcome: "transport" as const, value: null }));
    for (let i = 0; i < BREAKER_FAILURE_THRESHOLD; i += 1) {
      await breaker.run(failing);
    }

    time.advance(BREAKER_OPEN_MS);
    expect(breaker.state()).toBe("half-open");
    expect(breaker.allows()).toBe(true);

    await expect(breaker.run(async () => ({ outcome: "success", value: null }))).resolves.toEqual({ outcome: "success", value: null });
    expect(breaker.state()).toBe("closed");
    expect(breaker.failures()).toBe(0);
  });

  it("re-opens when the half-open probe fails again", async () => {
    const time = clock();
    const breaker = createProbeBreaker({ now: time.now });
    const failing = vi.fn(async () => ({ outcome: "transport" as const, value: null }));
    for (let i = 0; i < BREAKER_FAILURE_THRESHOLD; i += 1) {
      await breaker.run(failing);
    }

    time.advance(BREAKER_OPEN_MS);
    await breaker.run(failing);
    expect(breaker.state()).toBe("open");
    expect(breaker.allows()).toBe(false);
  });

  it("a success resets the streak before the threshold is reached", async () => {
    const time = clock();
    const breaker = createProbeBreaker({ now: time.now });

    await breaker.run(async () => ({ outcome: "transport", value: null }));
    await breaker.run(async () => ({ outcome: "transport", value: null }));
    await breaker.run(async () => ({ outcome: "success", value: null }));
    await breaker.run(async () => ({ outcome: "transport", value: null }));

    expect(breaker.state()).toBe("closed");
    expect(breaker.failures()).toBe(1);
  });

  it("degrades on an error a retry cannot fix and stops probing", async () => {
    const breaker = createProbeBreaker();
    const probe = vi.fn(async () => ({ outcome: "degraded" as const, value: null }));

    await breaker.run(probe);
    expect(breaker.state()).toBe("degraded");
    await expect(breaker.run(probe)).resolves.toBeNull();
    expect(probe).toHaveBeenCalledTimes(1);
  });

  it("a manual reset clears the open breaker", async () => {
    const time = clock();
    const breaker = createProbeBreaker({ now: time.now });
    const failing = vi.fn(async () => ({ outcome: "transport" as const, value: null }));
    for (let i = 0; i < BREAKER_FAILURE_THRESHOLD; i += 1) {
      await breaker.run(failing);
    }
    expect(breaker.state()).toBe("open");

    breaker.reset();
    expect(breaker.state()).toBe("closed");
    expect(breaker.allows()).toBe(true);
  });

  it("a manual reset clears a degraded breaker", async () => {
    const breaker = createProbeBreaker();
    await breaker.run(async () => ({ outcome: "degraded", value: null }));
    expect(breaker.state()).toBe("degraded");

    breaker.reset();
    expect(breaker.state()).toBe("closed");
    await expect(breaker.run(async () => ({ outcome: "success", value: null }))).resolves.toEqual({ outcome: "success", value: null });
  });

  it("reports how long until the next probe is allowed", async () => {
    const time = clock();
    const breaker = createProbeBreaker({ now: time.now });
    const failing = vi.fn(async () => ({ outcome: "transport" as const, value: null }));
    for (let i = 0; i < BREAKER_FAILURE_THRESHOLD; i += 1) {
      await breaker.run(failing);
    }

    expect(breaker.retryInMs()).toBe(BREAKER_OPEN_MS);
    time.advance(30_000);
    expect(breaker.retryInMs()).toBe(30_000);
    time.advance(30_000);
    expect(breaker.retryInMs()).toBe(0);
  });
});

describe("formatRetryCountdown", () => {
  it("reads minutes, rounded up, with a floor of one", () => {
    expect(formatRetryCountdown(60_000)).toBe("Retrying in 1 min");
    expect(formatRetryCountdown(61_000)).toBe("Retrying in 2 min");
    expect(formatRetryCountdown(240_000)).toBe("Retrying in 4 min");
  });

  it("is null when there is nothing to wait for", () => {
    expect(formatRetryCountdown(0)).toBeNull();
    expect(formatRetryCountdown(-5)).toBeNull();
  });
});
