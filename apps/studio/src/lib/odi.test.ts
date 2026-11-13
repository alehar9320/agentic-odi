/// <reference types="node" />
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import {
  formatMemberMean,
  formatOpportunityScore,
  hasScore,
  isUnderserved,
  isUnderservedPoint,
  opportunityPill,
  opportunityScore,
  scoredAverage,
  segmentBasisLine,
  summarizeMemberScores,
  underservedBoundaryImportance,
  UNDERSERVED_THRESHOLD,
} from "./odi";

// The fixture is the contract between the Python service and the TypeScript
// client. It lives in `packages/core/tests/fixtures/opportunity-score.json` and
// is read by both languages; neither side may re-derive its expected values.
const FIXTURE_PATH = resolve(
  dirname(fileURLToPath(import.meta.url)),
  "../../../../packages/core/tests/fixtures/opportunity-score.json",
);

function loadScoreFixture() {
  return JSON.parse(readFileSync(FIXTURE_PATH, "utf8")) as {
    formula: string;
    cases: Array<{
      id: string;
      importance: number | null;
      satisfaction: number | null;
      score: number | null;
    }>;
  };
}

describe("the shared scoring fixture", () => {
  it("is valid JSON with the documented formula and no comments", () => {
    const fixture = loadScoreFixture();
    expect(fixture.formula).toBe("importance + max(importance - satisfaction, 0)");
    expect(Array.isArray(fixture.cases)).toBe(true);
    expect(fixture.cases.length).toBeGreaterThan(0);
    // A comment would make the file invalid JSON, so parsing it is the check.
    expect(() => JSON.parse(readFileSync(FIXTURE_PATH, "utf8"))).not.toThrow();
  });

  it("covers importance 0-20, satisfaction above, equal and below, plus a null pair", () => {
    const fixture = loadScoreFixture();
    const importances = fixture.cases
      .map((c) => c.importance)
      .filter((v): v is number => v !== null);
    expect(Math.min(...importances)).toBe(0);
    expect(Math.max(...importances)).toBe(20);
    expect(fixture.cases.some((c) => c.importance === null && c.satisfaction === null)).toBe(true);
    expect(fixture.cases.some((c) => c.importance! > c.satisfaction!)).toBe(true);
    expect(fixture.cases.some((c) => c.importance! < c.satisfaction!)).toBe(true);
    expect(fixture.cases.some((c) => c.importance! === c.satisfaction!)).toBe(true);
  });

  it("agrees with the shared function on every scored case", () => {
    const fixture = loadScoreFixture();
    for (const c of fixture.cases) {
      if (c.importance === null || c.satisfaction === null) {
        expect(c.score).toBeNull();
        continue;
      }
      expect(opportunityScore(c.importance, c.satisfaction)).toBeCloseTo(c.score ?? 0, 5);
    }
  });

  it("fails when the fixture's expected value drifts from the function", () => {
    // The fixture is the contract: editing a case's `score` must break this
    // assertion, so the two sides cannot drift apart while each keeps passing.
    const fixture = loadScoreFixture();
    const drifted = {
      ...fixture,
      cases: fixture.cases.map((c) =>
        c.importance !== null && c.satisfaction !== null && c.score !== null
          ? { ...c, score: c.score + 1 }
          : c,
      ),
    };
    expect(() => {
      for (const c of drifted.cases) {
        if (c.importance === null || c.satisfaction === null || c.score === null) continue;
        expect(opportunityScore(c.importance, c.satisfaction)).toBeCloseTo(c.score, 5);
      }
    }).toThrow();
  });
});

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

  it("marks served outcomes green", () => {
    expect(opportunityPill(8)).toEqual({
      label: "✓ Served (Opp: 8.0)",
      variant: "green",
    });
  });

  // A missing score is not a verdict. The pill must not read "Served", and it
  // must not print "N/A" inside a sentence that claims something about the outcome.
  it("returns a neutral Not scored descriptor for a missing score", () => {
    expect(opportunityPill(null)).toEqual({ label: "Not scored", variant: "blue" });
    expect(opportunityPill(undefined)).toEqual({ label: "Not scored", variant: "blue" });
    expect(opportunityPill(null).label).not.toContain("Served");
    expect(opportunityPill(null).label).not.toContain("N/A");
  });
});

describe("the underserved boundary", () => {
  it("solves 2·importance − satisfaction = 10 for importance", () => {
    expect(underservedBoundaryImportance(0)).toBe(5);
    expect(underservedBoundaryImportance(4.9)).toBeCloseTo(7.45, 5);
    expect(underservedBoundaryImportance(10)).toBe(10);
  });

  it("agrees with isUnderserved at and around the boundary", () => {
    // At satisfaction 8 the boundary importance is (10 + 8) / 2 = 9, and the
    // values are exactly representable so the two rules cannot diverge on
    // floating-point noise rather than on the boundary itself.
    const cases: Array<[number, number, boolean]> = [
      [4, 8, false], // score 4 -> served
      [9, 8, false], // score 10 -> on the line, not underserved
      [9.5, 8, true], // score 11 -> underserved
      [5.5, 0, true], // score 11 -> underserved
    ];
    for (const [importance, satisfaction, expected] of cases) {
      expect(isUnderservedPoint(importance, satisfaction)).toBe(expected);
      expect(isUnderserved(opportunityScore(importance, satisfaction))).toBe(expected);
    }
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

describe("scoredAverage", () => {
  function outcome(score: number | null | undefined) {
    return { id: "O-1", opportunity_score: score } as never;
  }

  it("averages the stored scores only, never counting a missing score as zero", () => {
    const summary = scoredAverage([outcome(12), outcome(null)]);
    expect(summary.mean).toBeCloseTo(12, 5);
    expect(summary.scored).toBe(1);
    expect(summary.unscored).toBe(1);
  });

  it("reports no mean at all when nothing is scored", () => {
    const summary = scoredAverage([outcome(null), outcome(undefined)]);
    expect(summary.mean).toBeNull();
    expect(summary.scored).toBe(0);
    expect(summary.unscored).toBe(2);
  });

  it("averages the stored values, not the pre-rounded ones", () => {
    expect(scoredAverage([outcome(11.44), outcome(11.44)]).mean).toBeCloseTo(11.44, 5);
  });

  it("has no mean for an empty board rather than a zero", () => {
    const summary = scoredAverage([]);
    expect(summary.mean).toBeNull();
    expect(summary.scored).toBe(0);
    expect(summary.unscored).toBe(0);
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
