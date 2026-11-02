import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import {
  formatOpportunityScore,
  isUnderserved,
  opportunityPill,
  opportunityScore,
} from "./odi";

// The fixture is the contract between the Python service and the TypeScript
// client. It lives at packages/core/tests/fixtures/opportunity-score.json and
// is read by both this test and packages/core/tests/test_opportunity_score.py.
// Vitest runs with the studio package as its working directory, so the path
// from here is ../../packages/core/tests/fixtures/opportunity-score.json.
const FIXTURE = join(process.cwd(), "..", "..", "packages", "core", "tests", "fixtures", "opportunity-score.json");
const CASES = JSON.parse(readFileSync(FIXTURE, "utf8")).cases as Array<{
  name: string;
  importance: number | null;
  satisfaction: number | null;
  expected: number | null;
}>;

describe("opportunityScore (fixture-driven)", () => {
  for (const c of CASES) {
    it(`computes ${c.expected ?? "N/A"} for ${c.name}`, () => {
      if (c.importance == null || c.satisfaction == null) {
        expect(c.expected).toBeNull();
        return;
      }
      expect(opportunityScore(c.importance, c.satisfaction)).toBeCloseTo(c.expected, 5);
    });
  }
});

describe("opportunityScore (regression)", () => {
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