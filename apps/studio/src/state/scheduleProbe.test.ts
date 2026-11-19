import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  PROBE_BASE_MS,
  PROBE_JITTER,
  PROBE_MAX_MS,
  PROBE_SETTINGS_DEBOUNCE_MS,
  PROBE_STALE_MS,
  createProbeScheduler,
  nextProbeDelayMs,
  type VisibilityDocument,
} from "./scheduleProbe";

/** A document whose visibility the test drives, and which records its listeners. */
function fakeDocument() {
  const listeners = new Set<() => void>();
  const state = { visibilityState: "visible" as DocumentVisibilityState };
  const doc = {
    get visibilityState() {
      return state.visibilityState;
    },
    addEventListener: (_type: string, handler: () => void) => {
      listeners.add(handler);
    },
    removeEventListener: (_type: string, handler: () => void) => {
      listeners.delete(handler);
    },
  } as unknown as VisibilityDocument;
  return {
    doc,
    setVisibility(next: DocumentVisibilityState) {
      state.visibilityState = next;
      for (const handler of listeners) {
        handler();
      }
    },
    listenerCount: () => listeners.size,
  };
}

/** A deterministic clock the test advances by hand. */
function clock(start = 1_000_000) {
  let value = start;
  return {
    now: () => value,
    advance: (ms: number) => {
      value += ms;
    },
  };
}

describe("nextProbeDelayMs", () => {
  const midpoint = () => 0.5;

  it("walks the 30/60/120/240/300-second ladder at the midpoint", () => {
    const expected = [30_000, 60_000, 120_000, 240_000, 300_000];
    expected.forEach((ms, failures) => {
      expect(nextProbeDelayMs(failures, midpoint)).toBe(ms);
    });
  });

  it("caps the growth at five minutes however many fail", () => {
    expect(nextProbeDelayMs(12, midpoint)).toBe(PROBE_MAX_MS);
    expect(nextProbeDelayMs(100, midpoint)).toBe(PROBE_MAX_MS);
  });

  it("never lets the jitter push the wait past the cap", () => {
    // The highest jitter draw, on the cap, must still land on the cap.
    expect(nextProbeDelayMs(9, () => 1)).toBe(PROBE_MAX_MS);
  });

  it("keeps every jittered delay inside ±20% of the ladder", () => {
    const draws = [0, 0.25, 0.5, 0.75, 1];
    for (const failures of [0, 1, 2, 3]) {
      const base = Math.min(PROBE_MAX_MS, PROBE_BASE_MS * 2 ** failures);
      for (const draw of draws) {
        const delay = nextProbeDelayMs(failures, () => draw);
        expect(delay).toBeGreaterThanOrEqual(Math.floor(base * (1 - PROBE_JITTER)));
        expect(delay).toBeLessThanOrEqual(Math.ceil(base * (1 + PROBE_JITTER)));
      }
    }
  });

  it("treats a negative or fractional failure count as the base cadence", () => {
    expect(nextProbeDelayMs(-3, midpoint)).toBe(PROBE_BASE_MS);
    expect(nextProbeDelayMs(0.9, midpoint)).toBe(PROBE_BASE_MS);
  });
});

describe("createProbeScheduler", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("probes at the base cadence while the tab is visible", async () => {
    const { doc } = fakeDocument();
    let calls = 0;
    const scheduler = createProbeScheduler({
      probe: async () => {
        calls += 1;
        return true;
      },
      document: doc,
      random: () => 0.5,
    });
    scheduler.start();

    await vi.advanceTimersByTimeAsync(30_000);
    expect(calls).toBe(1);
    await vi.advanceTimersByTimeAsync(30_000);
    expect(calls).toBe(2);
    scheduler.stop();
  });

  it("makes no probe while the document is hidden, and none when it starts hidden", async () => {
    const fake = fakeDocument();
    fake.setVisibility("hidden");
    let calls = 0;
    const scheduler = createProbeScheduler({
      probe: async () => {
        calls += 1;
        return true;
      },
      document: fake.doc,
      random: () => 0.5,
    });
    scheduler.start();

    await vi.advanceTimersByTimeAsync(PROBE_MAX_MS * 3);
    expect(calls).toBe(0);
    scheduler.stop();
  });

  it("probes once on return only when the last answer has gone stale", async () => {
    const fake = fakeDocument();
    const time = clock();
    let calls = 0;
    const scheduler = createProbeScheduler({
      probe: async () => {
        calls += 1;
        return true;
      },
      document: fake.doc,
      random: () => 0.5,
      now: time.now,
    });
    scheduler.start();
    await vi.advanceTimersByTimeAsync(30_000);
    expect(calls).toBe(1);

    // Away and back within the staleness window: the answer still counts.
    fake.setVisibility("hidden");
    time.advance(5_000);
    fake.setVisibility("visible");
    await vi.advanceTimersByTimeAsync(0);
    expect(calls).toBe(1);

    // Away long enough that the answer is stale: one probe on return.
    fake.setVisibility("hidden");
    time.advance(PROBE_STALE_MS);
    fake.setVisibility("visible");
    await vi.advanceTimersByTimeAsync(0);
    expect(calls).toBe(2);
    scheduler.stop();
  });

  it("widens the gap after failures and returns to base after a success", async () => {
    const { doc } = fakeDocument();
    let calls = 0;
    let succeed = false;
    const scheduler = createProbeScheduler({
      probe: async () => {
        calls += 1;
        return succeed;
      },
      document: doc,
      random: () => 0.5,
    });
    scheduler.start();

    // First failure, then the wait is the second rung: 60 s.
    await vi.advanceTimersByTimeAsync(30_000);
    expect(calls).toBe(1);
    expect(scheduler.failures()).toBe(1);
    await vi.advanceTimersByTimeAsync(30_000);
    expect(calls, "nothing fires before the widened gap elapses").toBe(1);
    await vi.advanceTimersByTimeAsync(30_000);
    expect(calls).toBe(2);
    expect(scheduler.failures()).toBe(2);

    // A success resets the ladder to the base cadence.
    succeed = true;
    await vi.advanceTimersByTimeAsync(120_000);
    expect(calls).toBe(3);
    expect(scheduler.failures()).toBe(0);
    await vi.advanceTimersByTimeAsync(30_000);
    expect(calls).toBe(4);
    scheduler.stop();
  });

  it("counts one probe on each rung of the 30/60/120/240/300-second ladder", async () => {
    const { doc } = fakeDocument();
    let calls = 0;
    const scheduler = createProbeScheduler({
      probe: async () => {
        calls += 1;
        return false;
      },
      document: doc,
      random: () => 0.5,
    });
    scheduler.start();

    // The midpoint draw yields the exact ladder, so each rung is one probe: the
    // wait after N failures is the (N+1)th rung.
    const ladder = [30_000, 60_000, 120_000, 240_000, 300_000];
    for (const [index, wait] of ladder.entries()) {
      await vi.advanceTimersByTimeAsync(wait - 1);
      expect(calls, `no probe before rung ${index + 1} elapses`).toBe(index);
      await vi.advanceTimersByTimeAsync(1);
      expect(calls, `one probe on rung ${index + 1}`).toBe(index + 1);
    }

    // The cap holds: further waits stay at five minutes, one probe apiece.
    await vi.advanceTimersByTimeAsync(PROBE_MAX_MS);
    expect(calls).toBe(6);
    expect(scheduler.failures()).toBe(6);
    scheduler.stop();
  });

  it("resets the failure streak on a manual check", async () => {
    const { doc } = fakeDocument();
    let calls = 0;
    const scheduler = createProbeScheduler({
      probe: async () => {
        calls += 1;
        return false;
      },
      document: doc,
      random: () => 0.5,
    });
    scheduler.start();

    await vi.advanceTimersByTimeAsync(30_000);
    await vi.advanceTimersByTimeAsync(60_000);
    expect(scheduler.failures()).toBe(2);

    scheduler.check();
    await vi.advanceTimersByTimeAsync(0);
    expect(calls).toBe(3);
    expect(scheduler.failures()).toBe(1);
    scheduler.stop();
  });

  it("probes immediately on a manual check and re-arms from that result", async () => {
    const { doc } = fakeDocument();
    let calls = 0;
    const scheduler = createProbeScheduler({
      probe: async () => {
        calls += 1;
        return true;
      },
      document: doc,
      random: () => 0.5,
    });
    scheduler.start();

    scheduler.check();
    await vi.advanceTimersByTimeAsync(0);
    expect(calls).toBe(1);

    // The timer the check armed is the base cadence, not a leftover.
    await vi.advanceTimersByTimeAsync(29_000);
    expect(calls).toBe(1);
    await vi.advanceTimersByTimeAsync(1_000);
    expect(calls).toBe(2);
    scheduler.stop();
  });

  it("stops scheduling and forgets its visibility listener on stop", async () => {
    const fake = fakeDocument();
    let calls = 0;
    const scheduler = createProbeScheduler({
      probe: async () => {
        calls += 1;
        return true;
      },
      document: fake.doc,
      random: () => 0.5,
    });
    scheduler.start();
    expect(fake.listenerCount()).toBe(1);

    scheduler.stop();
    expect(fake.listenerCount()).toBe(0);

    await vi.advanceTimersByTimeAsync(PROBE_MAX_MS * 2);
    expect(calls).toBe(0);
    fake.setVisibility("visible");
    await vi.advanceTimersByTimeAsync(PROBE_MAX_MS);
    expect(calls).toBe(0);
  });

  it("exposes a settings debounce constant the caller can rely on", () => {
    expect(PROBE_SETTINGS_DEBOUNCE_MS).toBe(500);
  });
});
