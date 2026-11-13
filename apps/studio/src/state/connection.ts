import { asStudioError } from "../api/studioApi";
import type { SidecarLiveness } from "../types";

export type ProbeState = "unknown" | "live" | "degraded" | "down";

/** One probe: what was measured, when, and the one sentence that explains it. */
export interface ProbeResult {
  state: ProbeState;
  /** When the probe answered, in epoch milliseconds. Null before the first answer. */
  checked_at: number | null;
  /** Written here, never passed through: provider detail must not reach the screen. */
  message: string;
}

/**
 * What the studio currently believes about the three things it talks to.
 *
 * Liveness — is the process up — is kept apart from readiness — can it serve a
 * model — because a rejected API key is a problem with one row, not with the
 * application. Cadence is not this module's business: `next_check_at` is filled
 * by the scheduling slice (#535) and stays null until then.
 */
export interface ConnectionSnapshot {
  liveness: ProbeResult;
  model: ProbeResult;
  mcp: ProbeResult;
  /** Consecutive probes in which the process itself did not answer. */
  consecutive_failures: number;
  next_check_at: number | null;
}

const NOT_CHECKED = "Not checked yet.";
const SERVICE_DOWN = asStudioError(new TypeError("fetch failed")).message;

const LIVENESS_SENTENCE: Record<string, string> = {
  store_corrupt: "Running, but its store failed the integrity check.",
};

/** What the studio says about a model that was never given a chance to answer. */
export const LOCAL_MODEL_SENTENCE = "Answering from your device. No model connected.";

const MODEL_SENTENCE = {
  local: LOCAL_MODEL_SENTENCE,
  rejected_key: "Not ready — the endpoint rejected the key.",
  timeout: "Not ready — the endpoint did not answer in time.",
  refused: "Not ready — nothing is listening at that address.",
  unknown: "Not ready — the endpoint did not answer as expected.",
};

const OFFLINE_MARKERS = ["offline", "local studio mode"];
const KEY_MARKERS = ["401", "403", "api key", "unauthorized", "authentication", "invalid key"];
const TIMEOUT_MARKERS = ["timed out", "timeout"];
const REFUSED_MARKERS = [
  "connection refused",
  "connection error",
  "connection aborted",
  "failed to establish",
  "econnrefused",
];

function matchedBy(message: string, markers: string[]): boolean {
  const lower = message.toLowerCase();
  return markers.some((marker) => lower.includes(marker));
}

/** The sidecar's own answer, or a thrown failure, read as a model state. */
function modelSentence(message: string): { state: ProbeState; message: string } {
  if (matchedBy(message, OFFLINE_MARKERS)) {
    return { state: "down", message: MODEL_SENTENCE.local };
  }
  if (matchedBy(message, KEY_MARKERS)) {
    return { state: "degraded", message: MODEL_SENTENCE.rejected_key };
  }
  if (matchedBy(message, TIMEOUT_MARKERS)) {
    return { state: "degraded", message: MODEL_SENTENCE.timeout };
  }
  if (matchedBy(message, REFUSED_MARKERS)) {
    return { state: "down", message: MODEL_SENTENCE.refused };
  }
  return { state: "degraded", message: MODEL_SENTENCE.unknown };
}

function failedLiveness(previous: ConnectionSnapshot, liveness: ProbeResult): number {
  return liveness.state === "down" ? previous.consecutive_failures + 1 : 0;
}

export function emptySnapshot(): ConnectionSnapshot {
  const unknown: ProbeResult = { state: "unknown", checked_at: null, message: NOT_CHECKED };
  return {
    liveness: unknown,
    model: unknown,
    mcp: unknown,
    consecutive_failures: 0,
    next_check_at: null,
  };
}

export function livenessProbe(answer: SidecarLiveness): ProbeResult {
  if (!answer.ok) {
    return { state: "down", checked_at: answer.checked_at, message: SERVICE_DOWN };
  }
  if (answer.degraded) {
    return {
      state: "degraded",
      checked_at: answer.checked_at,
      message: LIVENESS_SENTENCE[answer.degraded.reason] ?? "Running, but the service reported a problem.",
    };
  }
  return { state: "live", checked_at: answer.checked_at, message: "The local Studio service is answering." };
}

export function modelProbe(
  answer: { healthy: boolean | null; message: string },
  checked_at: number,
): ProbeResult {
  if (answer.healthy === null) {
    return { state: "unknown", checked_at: null, message: NOT_CHECKED };
  }
  if (answer.healthy) {
    return { state: "live", checked_at, message: answer.message };
  }
  return { ...modelSentence(answer.message), checked_at };
}

export function mcpProbe(reachable: boolean, checked_at: number): ProbeResult {
  return reachable
    ? { state: "live", checked_at, message: "The MCP server is answering." }
    : { state: "down", checked_at, message: "Not ready — no MCP server answered." };
}

/** The process answered, even if what it answered with was a problem. */
export function isAlive(result: ProbeResult): boolean {
  return result.state === "live" || result.state === "degraded";
}

/** Nothing the probe could see is wrong. */
export function isReady(result: ProbeResult): boolean {
  return result.state === "live";
}

/**
 * `true` / `false` / null-for-not-measured, on the question "is the process answering".
 */
export function isAliveFlag(result: ProbeResult): boolean | null {
  return result.state === "unknown" ? null : isAlive(result);
}

/** The same three-state answer on the question "can it serve". */
export function isReadyFlag(result: ProbeResult): boolean | null {
  return result.state === "unknown" ? null : isReady(result);
}

export type ProbeTone = "ok" | "warn" | "unknown";

const TONE_FOR_STATE: Record<ProbeState, ProbeTone> = {
  unknown: "unknown",
  live: "ok",
  degraded: "warn",
  down: "warn",
};

/** The dot colour a row carries. Kept beside the states so a new state cannot slip past it. */
export function probeTone(result: ProbeResult): ProbeTone {
  return TONE_FOR_STATE[result.state];
}

/**
 * The word the sidecar row shows. The same state means something different for
 * the process than for the model, so the mapping lives beside the states.
 */
const LIVENESS_WORD: Record<ProbeState, string> = {
  unknown: "unknown",
  live: "reachable",
  degraded: "degraded",
  down: "unavailable",
};

/** The word the MCP row shows. A server nobody probed is not an offline server. */
const MCP_WORD: Record<ProbeState, string> = {
  unknown: "not checked",
  live: "connected",
  degraded: "offline",
  down: "offline",
};

export function livenessWord(result: ProbeResult): string {
  return LIVENESS_WORD[result.state];
}

export function mcpWord(result: ProbeResult): string {
  return MCP_WORD[result.state];
}

export function recordProbes(
  previous: ConnectionSnapshot,
  probes: { liveness: ProbeResult; mcp: ProbeResult; model: ProbeResult },
): ConnectionSnapshot {
  return {
    ...previous,
    ...probes,
    consecutive_failures: failedLiveness(previous, probes.liveness),
  };
}

/** Replace only the process answer: the boot diagnostics know about the store, not the model. */
export function withLiveness(previous: ConnectionSnapshot, liveness: ProbeResult): ConnectionSnapshot {
  return {
    ...previous,
    liveness,
    consecutive_failures: failedLiveness(previous, liveness),
  };
}
