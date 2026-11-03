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

export function formatOpportunityScore(score: number | null | undefined): string {
  if (score == null) {
    return "N/A";
  }
  return score.toFixed(1);
}

export function opportunityPill(score: number | null | undefined): PillDescriptor {
  const formatted = formatOpportunityScore(score);
  if (isUnderserved(score)) {
    return { label: `🔥 Underserved (Opp: ${formatted})`, variant: "amber" };
  }
  return { label: `✓ Served (Opp: ${formatted})`, variant: "green" };
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
