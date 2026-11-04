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

export interface ScoredAverage {
  mean: number | null;
  scored: number;
  unscored: number;
}

export function scoredAverage(outcomes: Outcome[]): ScoredAverage {
  const scores = outcomes
    .map((o) => o.opportunity_score)
    .filter((s): s is number => typeof s === "number");
  const scored = scores.length;
  const unscored = outcomes.length - scored;
  const mean = scored === 0 ? null : scores.reduce((a, b) => a + b, 0) / scored;
  return { mean, scored, unscored };
}
