import { describe, expect, it } from "vitest";

import {
  formatMemberMean,
  formatOpportunityScore,
  opportunityPill,
  UNSCORED_LABEL,
} from "./odi";
import { score } from "./records";

describe("score vocabulary parity", () => {
  it("spells a missing score one way across every surface", () => {
    expect(formatOpportunityScore(null)).toBe(UNSCORED_LABEL);
    expect(score(null)).toBe(UNSCORED_LABEL);
    expect(
      formatMemberMean({ mean: null, scored: 0, unscored: 2 }),
    ).toBe(UNSCORED_LABEL);
    expect(opportunityPill(undefined).label).toBe(UNSCORED_LABEL);
  });
});