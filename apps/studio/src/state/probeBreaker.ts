/**
 * One probe at a time, and a breaker for an endpoint that keeps refusing (#536).
 *
 * `scheduleProbe.ts` decides *when* the studio probes. This module decides
 * *whether* a probe may run and *what a refusal means*. Two things it owns:
 *
 * - **Single flight.** One promise is in flight at most. A second caller — an
 *   effect that re-armed, or a person pressing "Check now" — joins the promise
 *   already on the wire instead of starting a probe beside it, so a slow failure
 *   can never overwrite a fresh success.
 * - **A three-state breaker.** Consecutive retryable failures open it; while it
 *   is open no probe runs. After a fixed window one half-open probe is allowed:
 *   success closes the breaker, another failure opens it again. A refusal a
 *   retry cannot fix — a rejected key, a model that is not there — is a
 *   `degraded` answer instead: the breaker waits for a person to change the
 *   endpoint or ask again, rather than burning requests forever.
 *
 * Nothing here knows what a probe measures. The caller answers with a
 * `ProbeOutcome`, and `classifyProbeError` turns a thrown error into one.
 */

import { asStudioError, isTransportFailure } from "../api/studioApi";

/** Consecutive retryable failures that open the breaker. */
export const BREAKER_FAILURE_THRESHOLD = 3;

/** How long the breaker stays open before it allows one half-open probe. */
export const BREAKER_OPEN_MS = 60_000;

/**
 * What one probe concluded.
 *
 * - `success` — the endpoint answered.
 * - `transport` — nothing answered: the network or a proxy was silent.
 * - `retryable` — an answer a later retry may clear (a sidecar 5xx, a 429).
 * - `degraded` — an answer a retry cannot fix (a rejected key, a missing
 *   model). The breaker stops probing until it is reset.
 */
export type ProbeOutcome = "success" | "transport" | "retryable" | "degraded";

/** The three states a breaker is in, plus the parked `degraded` state. */
export type BreakerState = "closed" | "open" | "half-open" | "degraded";

/** Application error codes a retry cannot clear, so they park the breaker. */
const DEGRADED_CODES = new Set(["unauthorized", "not_found"]);

/**
 * Message shapes that name a refusal a retry cannot clear. The sidecar answers
 * `200` with a message for a rejected key or a missing model, so the words are
 * the only evidence of what happened — there is no error code to read.
 */
const DEGRADED_MESSAGE =
  /\b(401|403|unauthori[sz]ed|forbidden|invalid[\s-]*api[\s-]*key|incorrect[\s-]*api[\s-]*key|model[\s\S]*not[\s-]*found|no such model)\b/i;

/**
 * Classify a probe failure.
 *
 * A transport failure is one the network can clear. Any other failure is an
 * answer, and the answer decides whether a retry is worth making: a rejected
 * key or a model that is not there will be rejected again, so it degrades; a
 * sidecar 5xx or a 429 is worth another try, so it stays retryable. `message`
 * is the sidecar's own words, consulted when the failure arrived as a `200`.
 */
export function classifyProbeError(
  error: unknown,
  message = "",
): Exclude<ProbeOutcome, "success"> {
  if (isTransportFailure(error)) {
    return "transport";
  }
  if (DEGRADED_CODES.has(asStudioError(error).code) || DEGRADED_MESSAGE.test(message)) {
    return "degraded";
  }
  return "retryable";
}

export interface ProbeBreaker {
  /**
   * Run one probe, or join the one already in flight.
   *
   * Returns `null` without calling the probe when the breaker is open or
   * degraded, so a scheduled tick cannot spend a request the breaker forbids.
   * A joined caller receives the value the in-flight probe resolved with.
   */
  run<T>(probe: () => Promise<{ outcome: ProbeOutcome; value: T }>): Promise<
    { outcome: ProbeOutcome; value: T } | null
  >;
  /** Whether a probe may run right now. */
  allows(now?: number): boolean;
  /** The current state, resolving `open` to `half-open` once the window elapses. */
  state(now?: number): BreakerState;
  /** Milliseconds until a probe is allowed again; 0 when one is allowed now. */
  retryInMs(now?: number): number;
  /** Consecutive retryable failures since the last success or reset. */
  failures(): number;
  /** Close the breaker and forget the streak — a manual check, or a settings edit. */
  reset(): void;
}

export interface ProbeBreakerOptions {
  now?: () => number;
  /** Failures that open the breaker. Defaults to `BREAKER_FAILURE_THRESHOLD`. */
  threshold?: number;
  /** How long the breaker stays open. Defaults to `BREAKER_OPEN_MS`. */
  openMs?: number;
}

/**
 * Wrap a function so concurrent calls share one run.
 *
 * A scheduled tick and a person pressing "Check now" must not put two probes on
 * the wire: the second caller joins the promise the first one started, so a slow
 * failure can never land after a fresher success. The guard clears when the
 * promise settles, so the next call after it runs fresh.
 */
export function createSingleFlight<T>(run: () => Promise<T>): () => Promise<T> {
  let inFlight: Promise<T> | null = null;
  return () => {
    if (inFlight) {
      return inFlight;
    }
    const started = (async () => {
      try {
        return await run();
      } finally {
        inFlight = null;
      }
    })();
    inFlight = started;
    return started;
  };
}

/**
 * Create the single-flight breaker the studio's probes share.
 *
 * It is deliberately a plain object, not a hook: the scheduler owns the timer,
 * the context owns the lifetime, and this owns the policy, so the state machine
 * is readable and testable without a renderer.
 */
export function createProbeBreaker(options: ProbeBreakerOptions = {}): ProbeBreaker {
  const now = options.now ?? (() => Date.now());
  const threshold = options.threshold ?? BREAKER_FAILURE_THRESHOLD;
  const openMs = options.openMs ?? BREAKER_OPEN_MS;

  let failures = 0;
  let openUntil: number | null = null;
  let degraded = false;
  let inFlight: Promise<{ outcome: ProbeOutcome; value: unknown }> | null = null;

  function allowed(at: number): boolean {
    if (degraded) {
      return false;
    }
    return openUntil === null || at >= openUntil;
  }

  function record(outcome: ProbeOutcome, at: number): void {
    switch (outcome) {
      case "success":
        failures = 0;
        openUntil = null;
        return;
      case "degraded":
        degraded = true;
        return;
      case "transport":
      case "retryable":
        failures += 1;
        if (failures >= threshold) {
          openUntil = at + openMs;
        }
        return;
    }
  }

  return {
    run<T>(probe: () => Promise<{ outcome: ProbeOutcome; value: T }>) {
      if (inFlight) {
        return inFlight as Promise<{ outcome: ProbeOutcome; value: T }>;
      }
      const at = now();
      if (!allowed(at)) {
        return Promise.resolve(null);
      }
      const started = (async (): Promise<{ outcome: ProbeOutcome; value: T }> => {
        try {
          const { outcome, value } = await probe();
          record(outcome, now());
          return { outcome, value };
        } finally {
          inFlight = null;
        }
      })();
      inFlight = started;
      return started;
    },
    allows: (at) => allowed(at ?? now()),
    state(at) {
      const when = at ?? now();
      if (degraded) {
        return "degraded";
      }
      if (openUntil === null) {
        return "closed";
      }
      return when < openUntil ? "open" : "half-open";
    },
    retryInMs(at) {
      const when = at ?? now();
      if (openUntil === null || degraded) {
        return 0;
      }
      return Math.max(0, openUntil - when);
    },
    failures: () => failures,
    reset() {
      failures = 0;
      openUntil = null;
      degraded = false;
    },
  };
}

/**
 * The words for a countdown, or `null` when there is nothing to wait for.
 *
 * Minutes, rounded up, with a floor of one so a sub-minute wait never reads as
 * "Retrying in 0 min".
 */
export function formatRetryCountdown(ms: number): string | null {
  if (!Number.isFinite(ms) || ms <= 0) {
    return null;
  }
  const minutes = Math.max(1, Math.ceil(ms / 60_000));
  return `Retrying in ${minutes} min`;
}
