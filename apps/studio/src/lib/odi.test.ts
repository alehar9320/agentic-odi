import { describe, expect, it } from "vitest";

import {
  MIN_MEANINGFUL_N,
  confidenceClass,
  formatBand,
  formatBandProvenance,
  formatOpportunityScore,
  formatSample,
  isUnderserved,
  nAdvisory,
  opportunityPill,
  opportunityScore,
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

describe("formatSample", () => {
  it("reads as est. when the counts are unknown", () => {
    expect(formatSample({})).toBe("est.");
    expect(formatSample({ score_method: "estimate" })).toBe("est.");
  });

  it("never fabricates an n for an estimate with no counts", () => {
    expect(formatSample({ score_method: "estimate", importance_n: null, satisfaction_n: null })).toBe(
      "est.",
    );
  });

  it("shows one shared n and the method when the counts agree", () => {
    expect(formatSample({ score_method: "survey", importance_n: 40, satisfaction_n: 40 })).toBe(
      "n=40 (survey)",
    );
  });

  it("shows both counts when the dimensions differ", () => {
    expect(formatSample({ score_method: "survey", importance_n: 40, satisfaction_n: 12 })).toBe(
      "n=40/12 (survey)",
    );
  });

  it("marks a missing dimension with ? rather than inventing a count", () => {
    expect(formatSample({ score_method: "import", importance_n: 40, satisfaction_n: null })).toBe(
      "n=40/? (import)",
    );
  });

  it("falls back to est. when the method is absent but no counts exist", () => {
    expect(formatSample({ importance_n: null, satisfaction_n: null })).toBe("est.");
  });
});

describe("formatBand", () => {
  it("reads an estimate as no band, never a tight one", () => {
    expect(formatBand({ score_method: "estimate" })).toBe("no band");
  });

  it("renders a survey band as a range", () => {
    expect(
      formatBand({ score_method: "survey", opportunity_low: 8.5, opportunity_high: 10.5 }),
    ).toBe("8.5–10.5");
  });

  it("marks a zero-width survey band so it is not read as certainty", () => {
    expect(
      formatBand({ score_method: "survey", opportunity_low: 10, opportunity_high: 10 }),
    ).toBe("±0 (n=1)");
  });

  it("reads a missing band as no band", () => {
    expect(formatBand({ score_method: "survey" })).toBe("no band");
  });
});

describe("confidenceClass", () => {
  it("calls a large survey measured", () => {
    expect(confidenceClass({ score_method: "survey", importance_n: 40, satisfaction_n: 40 })).toBe(
      "measured",
    );
  });

  it("calls a small survey thin", () => {
    expect(confidenceClass({ score_method: "survey", importance_n: 3, satisfaction_n: 3 })).toBe(
      "thin",
    );
  });

  it("never treats a method label alone as evidence", () => {
    expect(confidenceClass({ score_method: "survey" })).toBe("none");
  });

  it("lets the weakest dimension bound the class", () => {
    expect(confidenceClass({ score_method: "survey", importance_n: 40, satisfaction_n: 2 })).toBe(
      "thin",
    );
  });
});

describe("formatBandProvenance", () => {
  it("says plainly when a score carries no band", () => {
    expect(formatBandProvenance(null)).toBe("no band");
    expect(formatBandProvenance({ outcome_id: "O-1", band: null })).toBe("no band");
  });

  it("names the sample, confidence and seed behind a stored band", () => {
    expect(
      formatBandProvenance({
        outcome_id: "O-1",
        band: {
          low: 14,
          high: 18,
          n: 40,
          confidence_level: 0.95,
          seed: 7,
          method: "survey",
          computed_at: "2026-01-01T00:00:00+00:00",
          stale: false,
        },
      }),
    ).toBe("n=40 · 95% · seed 7");
  });

  it("marks a stale band and an unrecorded seed rather than faking either", () => {
    expect(
      formatBandProvenance({
        outcome_id: "O-1",
        band: {
          low: 14,
          high: 18,
          n: 40,
          confidence_level: 0.95,
          seed: null,
          method: "survey",
          computed_at: "2026-01-01T00:00:00+00:00",
          stale: true,
        },
      }),
    ).toBe("n=40 · 95% · seed unrecorded · stale");
  });
});

describe("nAdvisory (M2-14)", () => {
  it("uses the documented threshold of 20", () => {
    expect(MIN_MEANINGFUL_N).toBe(20);
  });

  it("advises a four-response sample and names the number and threshold", () => {
    const advisory = nAdvisory({
      score_method: "survey",
      importance_n: 4,
      satisfaction_n: 4,
      opportunity_score: 12,
    });
    expect(advisory).not.toBeNull();
    expect(advisory?.n).toBe(4);
    expect(advisory?.threshold).toBe(20);
    expect(advisory?.dimension).toBe("both");
    expect(advisory?.message).toContain("4");
    expect(advisory?.message).toContain("20");
    expect(advisory?.message).toContain("below the advisory threshold");
  });

  it("does not advise a sample at or above the threshold", () => {
    expect(
      nAdvisory({ score_method: "survey", importance_n: 25, satisfaction_n: 25, opportunity_score: 12 }),
    ).toBeNull();
  });

  it("pins the boundary strictly below twenty", () => {
    expect(
      nAdvisory({ score_method: "survey", importance_n: 19, satisfaction_n: 19, opportunity_score: 12 }),
    ).not.toBeNull();
    expect(
      nAdvisory({ score_method: "survey", importance_n: 20, satisfaction_n: 20, opportunity_score: 12 }),
    ).toBeNull();
  });

  it("names the smaller dimension when the two differ", () => {
    const advisory = nAdvisory({
      score_method: "survey",
      importance_n: 40,
      satisfaction_n: 12,
      opportunity_score: 12,
    });
    expect(advisory?.n).toBe(12);
    expect(advisory?.dimension).toBe("satisfaction");
  });

  it("never advises an estimate or an unknown count at a fabricated zero", () => {
    expect(
      nAdvisory({ score_method: "estimate", opportunity_score: 12 }),
    ).toBeNull();
    expect(
      nAdvisory({ score_method: "survey", importance_n: null, satisfaction_n: null, opportunity_score: 12 }),
    ).toBeNull();
  });

  it("never advises an unscored outcome", () => {
    expect(
      nAdvisory({ score_method: "survey", importance_n: 3, satisfaction_n: 3, opportunity_score: null }),
    ).toBeNull();
  });
});
