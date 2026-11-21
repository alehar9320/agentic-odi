import { describe, expect, it } from "vitest";

import {
  formatMemberMean,
  formatOpportunityScore,
  opportunityPill,
  summarizeMemberScores,
  UNSCORED_LABEL,
} from "./odi";

import { score } from "./records";

describe("score vocabulary parity", () => {
  it("spells a missing score one way across every surface", () => {
    expect(formatOpportunityScore(null)).toBe(UNSCORED_LABEL);
    expect(score(null)).toBe(UNSCORED_LABEL);
    expect(formatMemberMean({ mean: null, scored: 0, unscored: 2 })).toBe(UNSCORED_LABEL);
    expect(opportunityPill(undefined).label).toBe(UNSCORED_LABEL);
  });

  it("a stored score of 0 still renders as 0.0 — it is scored", () => {
    expect(formatOpportunityScore(0)).toBe("0.0");
    expect(score(0)).toBe("0");
    expect(formatMemberMean(summarizeMemberScores([0, null]))).toContain("0.0");
    expect(opportunityPill(0).label).toContain("0.0");
  });
});