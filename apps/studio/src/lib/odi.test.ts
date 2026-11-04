import { describe, expect, it } from "vitest";

import {
  formatOpportunityScore,
  isUnderserved,
  opportunityPill,
  opportunityScore,
  scoredAverage,
  UNDERSERVED_THRESHOLD,
} from "./odi";

describe("opportunityScore", () => {
  it("computes importance + max(importance - satisfaction, 0)", () => {
    expect(opportunityScore(9.2, 3.1)).toBeCloseTo(15.3, 5);
  });

  it("never subtracts when satisfaction exceeds importance", () => {
    expect(opportunityScore(4, 9)).toBeCloseTo(4, 5);
    expect(opportunityScore(8, 8)).toBeCloseTo(8, 5);
  });
});

describe("isUnderserved", () => {
  it("is true only when the score is strictly greater than 10", () => {
    expect(isUnderserved(15.3)).toBe(true);
    expect(isUnderserved(10)).toBe(false);
    expect(isUnderserved(9.9)).toBe(false);
  });

  it("treats nullish scores as served", () => {
    expect(isUnderserved(null)).toBe(false);
    expect(isUnderserved(undefined)).toBe(false);
  });

  it("sits on the exported constant, not on a literal at the call site", () => {
    expect(UNDERSERVED_THRESHOLD).toBe(10);
    expect(isUnderserved(UNDERSERVED_THRESHOLD)).toBe(false);
    expect(isUnderserved(UNDERSERVED_THRESHOLD + 0.1)).toBe(true);
  });
});

describe("scoredAverage", () => {
  it("averages only the stored numeric scores", () => {
    const result = scoredAverage([
      { id: "O-1", opportunity_score: 12 },
      { id: "O-2" },
    ]);

    expect(result.mean).toBe(12);
    expect(result.scored).toBe(1);
    expect(result.unscored).toBe(1);
  });

  it("returns a null mean when nothing was scored", () => {
    const result = scoredAverage([{ id: "O-1" }, { id: "O-2", opportunity_score: null }]);

    expect(result.mean).toBeNull();
    expect(result.scored).toBe(0);
    expect(result.unscored).toBe(2);
  });

  it("averages the stored values, not pre-rounded ones", () => {
    const result = scoredAverage([
      { id: "O-1", opportunity_score: 11.44 },
      { id: "O-2", opportunity_score: 11.44 },
    ]);

    expect(result.mean).toBeCloseTo(11.44, 10);
    expect(result.scored).toBe(2);
    expect(result.unscored).toBe(0);
  });

  it("counts a zero as scored rather than treating it as absent", () => {
    const result = scoredAverage([{ id: "O-1", opportunity_score: 0 }]);

    expect(result.mean).toBe(0);
    expect(result.scored).toBe(1);
    expect(result.unscored).toBe(0);
  });

  it("returns a null mean for an empty list", () => {
    expect(scoredAverage([])).toEqual({ mean: null, scored: 0, unscored: 0 });
  });
});

describe("formatOpportunityScore (regression: crash when opp is None)", () => {
  it("renders N/A for nullish scores", () => {
    expect(formatOpportunityScore(null)).toBe("N/A");
    expect(formatOpportunityScore(undefined)).toBe("N/A");
  });

  it("formats real scores to one decimal", () => {
    expect(formatOpportunityScore(15.3)).toBe("15.3");
    expect(formatOpportunityScore(8)).toBe("8.0");
  });
});

describe("opportunityPill", () => {
  it("marks underserved outcomes with the amber badge", () => {
    expect(opportunityPill(15.3)).toEqual({
      label: "🔥 Underserved (Opp: 15.3)",
      variant: "amber",
    });
  });

  it("marks served outcomes green and never crashes on null", () => {
    expect(opportunityPill(null)).toEqual({
      label: "✓ Served (Opp: N/A)",
      variant: "green",
    });
  });
});
