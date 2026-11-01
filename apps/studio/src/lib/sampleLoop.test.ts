import { describe, expect, it } from "vitest";

import { sampleLoop, sampleRecordIds, isSampleRecord, SAMPLE_SOURCE } from "./sampleLoop";

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
    expect(isSampleRecord(loop.job)).toBe(true);
  });

  it("never answers true for a real record", () => {
    expect(isSampleRecord({ source: "local" })).toBe(false);
    expect(isSampleRecord({})).toBe(false);
    expect(isSampleRecord(null)).toBe(false);
  });

  it("names every id it created, so a cleanup deletes exactly those", () => {
    const ids = sampleRecordIds();
    expect(ids).toEqual(["sample-job", "sample-quote", "sample-outcome"]);
  });

  it("is frozen, so no scene can mutate the shared sample", () => {
    const loop = sampleLoop();
    expect(Object.isFrozen(loop)).toBe(true);
    expect(Object.isFrozen(loop.outcome)).toBe(true);
  });
});
