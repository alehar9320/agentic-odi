import type { Outcome } from "../types";
export interface PillDescriptor {
  label: string;
  variant: "amber" | "green" | "blue";
}

/** The line between "served" and "underserved". `packages/core` keeps its own
 * copy as `UNDERSERVED_SCORE`, and `tests/test_underserved_threshold_parity.py`
 * fails the moment the two disagree. */
export const UNDERSERVED_THRESHOLD = 10;

export function opportunityScore(importance: number, satisfaction: number): number {
  return importance + Math.max(importance - satisfaction, 0);
}

export function isUnderserved(score: number | null | undefined): boolean {
  return score != null && score > UNDERSERVED_THRESHOLD;
}

/** True only when the store actually holds a numeric score for this outcome.
 * A real score of `0` is scored; `null`, `undefined`, and non-finite values are not. */
export function hasScore(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

export function formatOpportunityScore(score: number | null | undefined): string {
  if (score == null) {
    return "N/A";
  }
  return score.toFixed(1);
}

export function opportunityPill(score: number | null | undefined): PillDescriptor {
  // A missing score is not "served". Saying so would read as a verdict the
  // store never reached, so it gets a neutral descriptor of its own.
  if (!hasScore(score)) {
    return { label: "Not scored", variant: "blue" };
  }
  const formatted = formatOpportunityScore(score);
  if (isUnderserved(score)) {
    return { label: `🔥 Underserved (Opp: ${formatted})`, variant: "amber" };
  }
  return { label: `✓ Served (Opp: ${formatted})`, variant: "green" };
}

/**
 * The importance at which an outcome's opportunity score crosses the threshold
 * for a given satisfaction: the solution of `2·importance − satisfaction =
 * UNDERSERVED_THRESHOLD` for importance. The underserved region sits above this
 * line, so the drawn zone and `isUnderserved(opportunityScore(...))` cannot
 * disagree.
 */
export function underservedBoundaryImportance(satisfaction: number): number {
  return (UNDERSERVED_THRESHOLD + satisfaction) / 2;
}

/**
 * The matrix's region test, in point space rather than score space. It is the
 * same rule as `isUnderserved(opportunityScore(importance, satisfaction))`, kept
 * separate so a plotted point and the shaded polygon share one boundary.
 */
export function isUnderservedPoint(importance: number, satisfaction: number): boolean {
  return importance > underservedBoundaryImportance(satisfaction);
}

/** What a group of member scores supports, with no score invented. */
export interface MemberScoreSummary {
  /** The mean of the members that carry a stored number, or null when none do. */
  mean: number | null;
  /** How many members carry a stored number. */
  scored: number;
  /** How many members carry none. A missing score is not a zero. */
  unscored: number;
}

/**
 * Summarize member scores without treating a missing score as a zero. The mean
 * divides by the scored members only, so one unscored outcome cannot drag the
 * group down, and an all-unscored group reports `null` rather than a fake `0`.
 */
export function summarizeMemberScores(
  scores: ReadonlyArray<number | null | undefined>,
): MemberScoreSummary {
  let total = 0;
  let scored = 0;
  let unscored = 0;
  for (const score of scores) {
    if (typeof score === "number" && Number.isFinite(score)) {
      total += score;
      scored += 1;
    } else {
      unscored += 1;
    }
  }
  return { mean: scored === 0 ? null : total / scored, scored, unscored };
}

/**
 * The landscape's headline average: the mean of the stored scores only. One
 * unscored outcome cannot drag the number down, and an all-unscored board has
 * no mean at all rather than a fake zero. Delegates the counting to
 * `summarizeMemberScores` so there is exactly one place that decides what
 * "scored" means.
 */
export function scoredAverage(outcomes: ReadonlyArray<Outcome>): MemberScoreSummary {
  return summarizeMemberScores(outcomes.map((outcome) => outcome.opportunity_score));
}

/**
 * The one sentence a segment board shows for its member scores. `Not scored`
 * replaces the mean when nothing is scored — never `0`, `NaN`, or a dash that
 * reads as a number.
 */
export function formatMemberMean(summary: MemberScoreSummary): string {
  if (summary.mean == null) {
    return "Not scored";
  }
  const base = `Mean opportunity ${summary.mean.toFixed(1)} across ${summary.scored} scored`;
  return summary.unscored > 0 ? `${base} · ${summary.unscored} not scored` : base;
}

/**
 * The one line a segment shows about where its people came from. An inferred
 * group is a candidate, not a researched market, and the board says so rather
 * than letting the two read alike.
 */
export function segmentBasisLine(peopleInferred: boolean): string {
  return peopleInferred
    ? "Candidate segment — grouped by the job it serves, not by researched people."
    : "People named from your evidence.";
}

/**
 * The one line an outcome card or table row shows for what it advances.
 *
 * The link is recorded at filing time, so the text shown is the objective's
 * text as it read then — a reworded vision leaves the old text behind as
 * drift evidence rather than silently updating the card. An outcome with no
 * link says plainly that it advances nothing yet, and never invents an
 * objective: a guess dressed as a record is the one thing this surface must
 * not do.
 */
export function formatAdvances(outcome: Outcome): string {
  const links = outcome.trace ?? [];
  if (links.length === 0) {
    return "Advances nothing yet";
  }
  const parts = links.map((link) => `${link.text} (${link.field})`);
  return `Advances ${parts.join(" · ")}`;
}

