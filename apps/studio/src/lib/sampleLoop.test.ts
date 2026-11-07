import { describe, expect, it } from "vitest";

import { isUnderserved, opportunityScore, UNDERSERVED_THRESHOLD } from "./odi";
import {
  SAMPLE_LOOP,
  SAMPLE_LOOP_DISMISSED_KEY,
  readSampleLoopDismissed,
  sampleSegmentLabel,
  writeSampleLoopDismissed,
  type SampleLoopStorage,
} from "./sampleLoop";

function memoryStorage(): SampleLoopStorage & { value: string | null } {
  const holder = {
    value: null as string | null,
    getItem: () => holder.value,
    setItem: (_key: string, value: string) => {
      holder.value = value;
    },
  };
  return holder;
}

describe("the sample loop", () => {
  it("is labelled as a sample and marked simulated", () => {
    expect(SAMPLE_LOOP.source).toBe("sample");
    expect(SAMPLE_LOOP.simulated).toBe(true);
  });

  it("computes its score with the client's own formula, not a literal", () => {
    expect(SAMPLE_LOOP.score).toBe(opportunityScore(SAMPLE_LOOP.importance, SAMPLE_LOOP.satisfaction));
    expect(SAMPLE_LOOP.score).toBe(opportunityScore(9, 3));
    expect(SAMPLE_LOOP.score).toBe(15);
  });

  it("is underserved by the shared threshold, not a separate string", () => {
    expect(isUnderserved(SAMPLE_LOOP.score)).toBe(true);
    expect(SAMPLE_LOOP.segment).toBe("underserved");
    expect(sampleSegmentLabel()).toBe("Underserved");
    expect(SAMPLE_LOOP.score).toBeGreaterThan(UNDERSERVED_THRESHOLD);
  });

  it("names all three gaps and nothing else", () => {
    expect(SAMPLE_LOOP.missing).toEqual([
      "one customer only",
      "no linked job step",
      "no second source",
    ]);
  });

  it("carries no count, percentage, price, date, or named company", () => {
    const text = [
      SAMPLE_LOOP.quote,
      SAMPLE_LOOP.sourceLabel,
      SAMPLE_LOOP.outcome,
      ...SAMPLE_LOOP.missing,
    ].join(" ");
    expect(text).not.toMatch(/\d/);
    expect(text).not.toMatch(/[$€£]|%|percent/i);
  });
});

describe("sample loop dismissal", () => {
  it("reads as not hidden when nothing is stored", () => {
    expect(readSampleLoopDismissed(memoryStorage())).toBe(false);
    expect(readSampleLoopDismissed(null)).toBe(false);
  });

  it("survives a reload through the stored key", () => {
    const storage = memoryStorage();
    writeSampleLoopDismissed(storage);

    expect(storage.value).toBe("1");
    expect(storage.getItem(SAMPLE_LOOP_DISMISSED_KEY)).toBe("1");
    expect(readSampleLoopDismissed(storage)).toBe(true);
  });
});
