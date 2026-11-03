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

/** Average of the scores the store actually holds. Outcomes that were never
 * scored are counted, never treated as a zero. `mean` is `null` when nothing
 * was scored — the caller decides what to show then. */
export function scoredAverage(outcomes: Outcome[]): {
  mean: number | null;
  scored: number;
  unscored: number;
} {
  let sum = 0;
  let scored = 0;
  let unscored = 0;
  for (const outcome of outcomes) {
    const score = outcome.opportunity_score;
    if (typeof score === "number" && Number.isFinite(score)) {
      sum += score;
      scored += 1;
    } else {
      unscored += 1;
    }
  }
  return {
    mean: scored ? sum / scored : null,
    scored,
    unscored,
  };
}
