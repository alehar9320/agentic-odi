import { describe, expect, it } from "vitest";

import { opportunityScore } from "./odi";
import {
  sampleLoop,
  sampleRecordIds,
  scoreSampleOutcome,
  isSampleRecord,
  SAMPLE_SOURCE,
} from "./sampleLoop";

describe("the sample brief", () => {
  it("is one fixed dataset with one quote and one unscored outcome", () => {
    const loop = sampleLoop();

    expect(loop.quote.content).toBe(
      "I keep a spreadsheet of config keys because I can't tell which ones are live.",
    );
    expect(loop.quote.source_name).toBe("one onboarding call, sample");
    // One outcome, and it carries no number: the tour scores it.
    expect(loop.outcome.importance).toBeNull();
    expect(loop.outcome.satisfaction).toBeNull();
    expect(loop.outcome.opportunity_score).toBeNull();
    expect(loop.missingEvidence).toHaveLength(3);
  });

  it("offers exactly three readings of the quote: the job, a workaround, a solution", () => {
    const loop = sampleLoop();

    expect(loop.interpretations).toHaveLength(3);
    expect(loop.interpretations.map((option) => option.kind)).toEqual([
      "job",
      "workaround",
      "solution",
    ]);
    expect(loop.interpretations[0].text).toBe("Know which config is live before shipping.");
  });

  it("scores the outcome with the real formula, never a hard-coded number", () => {
    const scored = scoreSampleOutcome(9, 3);

    expect(scored.opportunity_score).toBe(opportunityScore(9, 3));
    expect(scored.opportunity_score).toBe(15);
    expect(scored.importance).toBe(9);
    expect(scored.satisfaction).toBe(3);
    // A different pair recomputes, so the number is derived rather than fixed.
    expect(scoreSampleOutcome(9, 9).opportunity_score).toBe(9);
  });

  it("carries two comparisons scored by the same formula", () => {
    const loop = sampleLoop();

    expect(loop.comparisons).toHaveLength(2);
    expect(loop.comparisons.map((outcome) => outcome.opportunity_score)).toEqual([10, 14]);
  });

  it("is created only once, even when the tour restarts", () => {
    const first = sampleLoop();
    const second = sampleLoop();
    // The same object, not a copy: a restart cannot mint a second sample.
    expect(second).toBe(first);
  });

  it("is labelled as sample everywhere it appears", () => {
    const loop = sampleLoop();
    expect(loop.source).toBe(SAMPLE_SOURCE);
    expect(loop.simulated).toBe(true);
    expect(loop.job.source).toBe(SAMPLE_SOURCE);
    expect(loop.quote.source).toBe(SAMPLE_SOURCE);
    expect(loop.outcome.source).toBe(SAMPLE_SOURCE);
    expect(loop.comparisons.every((outcome) => outcome.source === SAMPLE_SOURCE)).toBe(true);
    expect(isSampleRecord(loop.job)).toBe(true);
  });

  it("links the outcome to the quote's evidence record", () => {
    const loop = sampleLoop();
    expect(loop.quote.outcome_id).toBe(loop.outcome.id);
  });

  it("never answers true for a real record", () => {
    expect(isSampleRecord({ source: "local" })).toBe(false);
    expect(isSampleRecord({})).toBe(false);
    expect(isSampleRecord(null)).toBe(false);
  });

  it("names every id it created, so a cleanup deletes exactly those", () => {
    const ids = sampleRecordIds();
    expect(ids).toEqual([
      "sample-job",
      "sample-quote",
      "sample-outcome",
      "sample-outcome-rollback",
      "sample-outcome-blame",
    ]);
  });

  it("is frozen, so no scene can mutate the shared sample", () => {
    const loop = sampleLoop();
    expect(Object.isFrozen(loop)).toBe(true);
    expect(Object.isFrozen(loop.outcome)).toBe(true);
    expect(Object.isFrozen(loop.interpretations)).toBe(true);
  });
});

