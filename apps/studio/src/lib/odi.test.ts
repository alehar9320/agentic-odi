import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import {
  formatMemberMean,
  formatOpportunityScore,
  hasScore,
  isUnderserved,
  opportunityPill,
  opportunityScore,
  segmentBasisLine,
  summarizeMemberScores,
  UNDERSERVED_THRESHOLD,
} from "./odi";

interface OpportunityScoreRow {
  importance: number;
  satisfaction: number;
  score: number;
  underserved: boolean;
}

// Vitest runs with the studio package as its working directory.
const SHARED_FIXTURE = join(
  process.cwd(),
  "../../packages/core/tests/fixtures/opportunity_scores.json",
);
const SHARED_ROWS = JSON.parse(readFileSync(SHARED_FIXTURE, "utf8")) as OpportunityScoreRow[];

describe("opportunityScore", () => {
  it("computes importance + max(importance - satisfaction, 0)", () => {
    expect(opportunityScore(9.2, 3.1)).toBeCloseTo(15.3, 5);
  });

  it("never subtracts when satisfaction exceeds importance", () => {
    expect(opportunityScore(4, 9)).toBeCloseTo(4, 5);
    expect(opportunityScore(8, 8)).toBeCloseTo(8, 5);
  });
});

describe("opportunityScore against packages/core's fixture", () => {
  it("explains every committed row the same way Python does", () => {
    expect(SHARED_ROWS).toHaveLength(5);
    for (const row of SHARED_ROWS) {
      const score = opportunityScore(row.importance, row.satisfaction);
      expect(score, `${row.importance}/${row.satisfaction}`).toBeCloseTo(row.score, 5);
      expect(isUnderserved(score), `${row.importance}/${row.satisfaction}`).toBe(row.underserved);
    }
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

describe("hasScore", () => {
  it("is true only for a finite number", () => {
    expect(hasScore(12.5)).toBe(true);
    expect(hasScore(0)).toBe(true); // a real score of zero is scored
    expect(hasScore(null)).toBe(false);
    expect(hasScore(undefined)).toBe(false);
    expect(hasScore(NaN)).toBe(false);
    expect(hasScore(Infinity)).toBe(false);
    expect(hasScore("12.5")).toBe(false);
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

describe("summarizeMemberScores", () => {
  it("averages only the members that carry a stored score", () => {
    const summary = summarizeMemberScores([16, 12, null]);
    expect(summary.mean).toBeCloseTo(14, 5);
    expect(summary.scored).toBe(2);
    expect(summary.unscored).toBe(1);
  });

  it("reports no mean rather than a zero when nothing is scored", () => {
    const summary = summarizeMemberScores([null, undefined]);
    expect(summary.mean).toBeNull();
    expect(summary.scored).toBe(0);
    expect(summary.unscored).toBe(2);
  });

  it("treats a missing score as missing, never as zero", () => {
    // A mean that counted the missing score as 0 would read 6.0, not 12.0.
    expect(summarizeMemberScores([12, null]).mean).toBeCloseTo(12, 5);
  });
});

describe("formatMemberMean", () => {
  it("names the mean, the scored count, and the unscored count", () => {
    expect(formatMemberMean(summarizeMemberScores([12, null]))).toBe(
      "Mean opportunity 12.0 across 1 scored · 1 not scored",
    );
  });

  it("omits the unscored clause when every member is scored", () => {
    expect(formatMemberMean(summarizeMemberScores([12, 16]))).toBe(
      "Mean opportunity 14.0 across 2 scored",
    );
  });

  it("renders Not scored instead of a fake zero, NaN, or dash", () => {
    expect(formatMemberMean(summarizeMemberScores([null, undefined]))).toBe("Not scored");
  });
});

describe("segmentBasisLine", () => {
  it("calls an inferred group a candidate, not a researched market", () => {
    expect(segmentBasisLine(true)).toBe(
      "Candidate segment — grouped by the job it serves, not by researched people.",
    );
  });

  it("claims only that the people were named when they were", () => {
    expect(segmentBasisLine(false)).toBe("People named from your evidence.");
  });
});
