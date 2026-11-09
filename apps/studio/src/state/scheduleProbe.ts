/**
 * When the studio probes its connections, and how long it waits after a refusal.
 *
 * The cadence is a statement about the person, not about the network: a tab
 * nobody is looking at makes no request at all, and an endpoint that keeps
 * refusing is asked less and less often. This module owns that policy and the
 * single timer that carries it, so there is one place to read and one place to
 * test. It knows nothing about what a probe measures — the caller answers
 * whether one succeeded.
 */

/** The cadence while the tab is visible and the last probe succeeded. */
export const PROBE_BASE_MS = 30_000;

/** The longest the studio will wait between probes, however many fail in a row. */
export const PROBE_MAX_MS = 300_000;

/** How far a delay may drift, up or down, so many tabs do not march in step. */
export const PROBE_JITTER = 0.2;

/** A wake probe is only worth making when the last answer is at least this old. */
export const PROBE_STALE_MS = PROBE_BASE_MS;

/** A settings edit settles for this long before it earns one probe. */
export const PROBE_SETTINGS_DEBOUNCE_MS = 500;

/**
 * The delay before the next probe: the base doubled once per consecutive
 * failure, capped at five minutes, then jittered by ±`PROBE_JITTER` and clamped
 * back to the cap so the wait never exceeds it. A `random` of 0.5 is the
 * midpoint and yields the exact 30/60/120/240/300-second ladder.
 */
export function nextProbeDelayMs(
  consecutiveFailures: number,
  random: () => number = Math.random,
): number {
  const failures = Math.max(0, Math.floor(consecutiveFailures));
  // 2 ** failures overflows to Infinity quickly; the cap makes that harmless.
  const growth = PROBE_BASE_MS * 2 ** failures;
  const capped = Math.min(PROBE_MAX_MS, growth);
  const jitter = 1 + PROBE_JITTER * (random() * 2 - 1);
  return Math.round(Math.min(PROBE_MAX_MS, capped * jitter));
}

export type VisibilityDocument = Pick<
  Document,
  "visibilityState" | "addEventListener" | "removeEventListener"
>;

export interface ProbeSchedulerOptions {
  /** Run one probe; resolve `true` when it succeeded, `false` when it did not. */
  probe: () => Promise<boolean>;
  random?: () => number;
  now?: () => number;
  /** The document whose visibility gates the timer. `null` schedules unconditionally. */
  document?: VisibilityDocument | null;
  timers?: {
    setTimeout: (handler: () => void, ms: number) => ReturnType<typeof setTimeout>;
    clearTimeout: (handle: ReturnType<typeof setTimeout>) => void;
  };
}

export interface ProbeScheduler {
  /** Begin scheduling. Idempotent, so a resume does not stack a second timer. */
  start(): void;
  /** Stop scheduling and cancel the pending timer. Idempotent. */
  stop(): void;
  /** Probe now, then re-arm from the result. The manual "Check now". */
  check(): Promise<void>;
  /** Forget the failure streak and re-arm at the base cadence. */
  reset(): void;
  /** Consecutive probes that did not succeed. */
  failures(): number;
}

const DEFAULT_TIMERS = {
  setTimeout: (handler: () => void, ms: number) => setTimeout(handler, ms),
  clearTimeout: (handle: ReturnType<typeof setTimeout>) => clearTimeout(handle),
};

/**
 * The one timer that decides when the next probe runs.
 *
 * It reschedules itself from each result rather than firing on a fixed interval,
 * so a refusal can widen the gap. While the document is hidden the timer is
 * cancelled outright; on return it probes once, but only if the last answer has
 * gone stale. The caller owns what a probe does and what a refusal means.
 */
export function createProbeScheduler(options: ProbeSchedulerOptions): ProbeScheduler {
  const probe = options.probe;
  const random = options.random ?? Math.random;
  const now = options.now ?? (() => Date.now());
  const doc =
    options.document ?? (typeof document === "undefined" ? null : document);
  const timers = options.timers ?? DEFAULT_TIMERS;

  let handle: ReturnType<typeof setTimeout> | null = null;
  let failures = 0;
  let lastCheckedAt: number | null = null;
  let running = false;

  function visible(): boolean {
    return doc === null || doc.visibilityState === "visible";
  }

  function clear(): void {
    if (handle !== null) {
      timers.clearTimeout(handle);
      handle = null;
    }
  }

  function arm(): void {
    clear();
    if (!running || !visible()) {
      return;
    }
    handle = timers.setTimeout(fire, nextProbeDelayMs(failures, random));
  }

  function fire(): void {
    handle = null;
    void run();
  }

  async function run(): Promise<void> {
    if (!running || !visible()) {
      return;
    }
    const ok = await probe();
    lastCheckedAt = now();
    failures = ok ? 0 : failures + 1;
    arm();
  }

  function onVisibility(): void {
    if (!running) {
      return;
    }
    if (!visible()) {
      clear();
      return;
    }
    const elapsed = lastCheckedAt === null ? Number.POSITIVE_INFINITY : now() - lastCheckedAt;
    if (Math.max(0, elapsed) >= PROBE_STALE_MS) {
      clear();
      void run();
    } else {
      arm();
    }
  }

  return {
    start() {
      if (!running) {
        running = true;
        doc?.addEventListener("visibilitychange", onVisibility);
      }
      arm();
    },
    stop() {
      running = false;
      clear();
      doc?.removeEventListener("visibilitychange", onVisibility);
    },
    check() {
      // A manual check is a reset: the person is asking again, so the streak
      // that widened the gap no longer describes the endpoint they just edited.
      failures = 0;
      clear();
      return run();
    },
    reset() {
      failures = 0;
      arm();
    },
    failures: () => failures,
  };
}
