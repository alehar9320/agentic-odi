import { describe, expect, it } from "vitest";

import { isUnderserved } from "./odi";
import {
  SAMPLE_EVIDENCE_ID,
  SAMPLE_EVIDENCE_IDS,
  SAMPLE_JOB_ID,
  SAMPLE_OUTCOME_ID,
  SAMPLE_OUTCOME_IDS,
  SAMPLE_STEP_ID,
  sampleCanvas,
  sampleRecordsForTour,
} from "./sampleLoop";

describe("sample brief", () => {
  it("is the sample job, step, evidence, and three scored outcomes", () => {
    const canvas = sampleCanvas();

    expect(canvas.jobs.map((job) => job.id)).toEqual([SAMPLE_JOB_ID]);
    expect(canvas.steps.map((step) => step.id)).toEqual([SAMPLE_STEP_ID]);
    expect(canvas.evidence?.map((item) => item.id)).toEqual([...SAMPLE_EVIDENCE_IDS]);
    expect(canvas.outcomes.map((outcome) => outcome.id)).toEqual([...SAMPLE_OUTCOME_IDS]);
    // Bundled sample data, never the person's live canvas.
    expect(canvas.source).toBe("seed");
  });

  it("scores the sample outcome as underserved so the highlight has a reason", () => {
    const canvas = sampleCanvas();
    const landed = canvas.outcomes.find((outcome) => outcome.id === SAMPLE_OUTCOME_ID);

    expect(landed).toBeDefined();
    expect(landed?.opportunity_score).toBe(15);
    expect(isUnderserved(landed?.opportunity_score)).toBe(true);
  });

  it("names every record the tour made, for removal", () => {
    const records = sampleRecordsForTour();

    expect(records).toContainEqual({ kind: "evidence", id: SAMPLE_EVIDENCE_ID });
    expect(records).toContainEqual({ kind: "step", id: SAMPLE_STEP_ID });
    expect(records).toContainEqual({ kind: "job", id: SAMPLE_JOB_ID });
    expect(records.filter((record) => record.kind === "outcome")).toHaveLength(
      SAMPLE_OUTCOME_IDS.length,
    );
  });

  it("returns a fresh canvas each call so a scene cannot mutate the sample", () => {
    const first = sampleCanvas();
    first.jobs[0].name = "changed";

    expect(sampleCanvas().jobs[0].name).not.toBe("changed");
  });
});
