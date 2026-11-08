import { describe, expect, it } from "vitest";

import { SAMPLE_JOB_ID, SAMPLE_OUTCOME_ID, SAMPLE_QUOTE_ID, isSampleRecord, sampleLoop } from "./sampleLoop";

describe("sampleLoop", () => {
  it("is created only once, even if the tour restarts", () => {
    expect(sampleLoop()).toBe(sampleLoop());
    expect(sampleLoop()).toBe(sampleLoop());
  });

  it("is frozen, so a scene cannot edit the one sample", () => {
    expect(Object.isFrozen(sampleLoop())).toBe(true);
  });

  it("carries one quote and one unscored outcome", () => {
    const sample = sampleLoop();
    expect(sample.quote.text).toContain("spreadsheet of config keys");
    expect(sample.outcome.importance).toBeNull();
    expect(sample.outcome.satisfaction).toBeNull();
    expect(sample.outcome.opportunity_score).toBeNull();
  });

  it("labels every record as a sample", () => {
    const sample = sampleLoop();
    expect(sample.source).toBe("sample");
    expect(sample.simulated).toBe(true);
    expect(sample.quote.source).toContain("sample");
  });

  it("knows only its own ids, so a real record is never removed", () => {
    expect(isSampleRecord({ id: SAMPLE_JOB_ID })).toBe(true);
    expect(isSampleRecord({ id: SAMPLE_QUOTE_ID })).toBe(true);
    expect(isSampleRecord({ id: SAMPLE_OUTCOME_ID })).toBe(true);
    expect(isSampleRecord({ id: "job-123" })).toBe(false);
    expect(isSampleRecord(null)).toBe(false);
  });
});
