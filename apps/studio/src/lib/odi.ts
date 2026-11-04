import type { Outcome } from "../types";

export interface PillDescriptor {
  label: string;
  variant: "amber" | "green" | "blue";
}

export interface ScoredAverage {
  /** Mean of the stored numeric scores, or `null` when none were stored. */
  mean: number | null;
  scored: number;
  unscored: number;
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

/**
 * Average only the outcomes that store a numeric `opportunity_score`. An outcome
 * nobody scored is not a zero: counting it as one invents a low score. The mean
 * is returned unrounded so callers round once, at display.
 */
export function scoredAverage(outcomes: Outcome[]): ScoredAverage {
  let sum = 0;
  let scored = 0;
  for (const outcome of outcomes) {
    if (typeof outcome.opportunity_score === "number") {
      sum += outcome.opportunity_score;
      scored += 1;
    }
  }
  return {
    mean: scored === 0 ? null : sum / scored,
    scored,
    unscored: outcomes.length - scored,
  };
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
