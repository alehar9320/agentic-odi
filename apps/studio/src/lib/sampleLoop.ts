import type { SegmentVerdict } from "../types";
import { isUnderserved, opportunityScore } from "./odi";

/**
 * The one sample loop the empty stage shows, as data (issue #318, honoring #78).
 *
 * A person who has never seen the method run gets one finished pass: the
 * customer's words, the outcome they imply, the score two numbers produce, and
 * the evidence still missing. It is typed, never fetched, and never written to
 * the store. Rendering it must leave IndexedDB, the canvas, the brief, the bell,
 * and the rail counts untouched, and nothing here may read as the person's own
 * measurement.
 *
 * It is the empty stage's first loop, and it shares its fixture with the tour
 * (#315): the tour walks the loop, this shows it finished.
 */
export interface SampleLoop {
  /** Provenance. Always `"sample"`, so no surface can mistake it for real work. */
  source: "sample";
  /** Whether the record is fabricated. Always true; nothing here is a measurement. */
  simulated: true;
  /** The customer's words, verbatim. */
  quote: string;
  /**
   * Where the quote came from — a hypothetical call, never a named company or
   * role that could be read as a real source.
   */
  sourceLabel: string;
  /** The outcome the quote implies, in ODI form. */
  outcome: string;
  importance: number;
  satisfaction: number;
  /**
   * Computed at module load with the client's own formula, never hard-coded, so
   * a change to the formula cannot leave the sample lying.
   */
  score: number;
  /** The band the score falls in. The label is derived from the threshold, not here. */
  segment: SegmentVerdict;
  /** What the sample does not yet prove. The gap is the part that teaches. */
  missing: string[];
}

const SAMPLE_IMPORTANCE = 9;
const SAMPLE_SATISFACTION = 3;
// Computed once, with the client's own formula, so a change to the formula
// cannot leave the sample lying.
const SAMPLE_SCORE = opportunityScore(SAMPLE_IMPORTANCE, SAMPLE_SATISFACTION);

export const SAMPLE_LOOP: SampleLoop = {
  source: "sample",
  simulated: true,
  quote: "I keep a spreadsheet of config keys because I can't tell which ones are live.",
  sourceLabel: "hypothetical onboarding call",
  outcome:
    "Minimize the time it takes to confirm which config keys are live before a deploy.",
  importance: SAMPLE_IMPORTANCE,
  satisfaction: SAMPLE_SATISFACTION,
  score: SAMPLE_SCORE,
  // The band comes from the shared threshold, not a second opinion.
  segment: isUnderserved(SAMPLE_SCORE) ? "underserved" : "appropriately_served",
  missing: ["one customer only", "no linked job step", "no second source"],
};

/** The label the threshold produces for the sample. Never a second source of truth. */
export function sampleSegmentLabel(loop: SampleLoop = SAMPLE_LOOP): string {
  return loop.segment === "underserved" ? "Underserved" : "Served";
}

export const SAMPLE_LOOP_DISMISSED_KEY = "studio.sampleLoopDismissed";

export type SampleLoopStorage = Pick<Storage, "getItem" | "setItem">;

function browserStorage(): SampleLoopStorage | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

/** Whether the person has hidden the sample. A missing key reads as "not hidden". */
export function readSampleLoopDismissed(
  storage: SampleLoopStorage | null = browserStorage(),
): boolean {
  if (!storage) {
    return false;
  }
  try {
    return storage.getItem(SAMPLE_LOOP_DISMISSED_KEY) === "1";
  } catch {
    return false;
  }
}

/** Hide the sample for good. There is no setting to bring it back. */
export function writeSampleLoopDismissed(
  storage: SampleLoopStorage | null = browserStorage(),
): void {
  if (!storage) {
    return;
  }
  try {
    storage.setItem(SAMPLE_LOOP_DISMISSED_KEY, "1");
  } catch {
    // Storage denied: the sample is dismissed for this session only.
  }
}
