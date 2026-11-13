import type { ConnectionSnapshot, ProbeResult, ProbeState } from "../state/connection";
import { emptySnapshot, recordProbes } from "../state/connection";

const CHECKED_AT = 1_700_000_000_000;

/** A probe answer a component test can name in one line. */
export function probeResult(state: ProbeState, message: string): ProbeResult {
  return { state, checked_at: state === "unknown" ? null : CHECKED_AT, message };
}

/**
 * A snapshot with the rows a test cares about and nothing else.
 *
 * Rows left out stay `unknown`, which is what a studio that has not probed them
 * holds — the same state a person sees before the first answer lands.
 */
export function snapshotOf(
  rows: Partial<Record<"liveness" | "model" | "mcp", ProbeResult>>,
): ConnectionSnapshot {
  return recordProbes(emptySnapshot(), {
    liveness: rows.liveness ?? probeResult("unknown", "Not checked yet."),
    mcp: rows.mcp ?? probeResult("unknown", "Not checked yet."),
    model: rows.model ?? probeResult("unknown", "Not checked yet."),
  });
}
