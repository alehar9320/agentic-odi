import { describe, expect, it, vi } from "vitest";

import type { CanvasData } from "../types";
import { SAMPLE_JOB_ID, SAMPLE_OUTCOME_ID, sampleRecordsForTour } from "../lib/sampleLoop";
import {
  planSampleRemoval,
  removeSampleRecords,
  sampleRecordsIn,
  type SampleCleanupActions,
} from "./sampleCleanup";

function actions(): SampleCleanupActions & {
  removed: { kind: string; id: string }[];
} {
  const removed: { kind: string; id: string }[] = [];
  return {
    removed,
    deleteEvidence: vi.fn(async (id: string) => {
      removed.push({ kind: "evidence", id });
    }),
    deleteOutcome: vi.fn(async (id: string) => {
      removed.push({ kind: "outcome", id });
    }),
    deleteStep: vi.fn(async (id: string) => {
      removed.push({ kind: "step", id });
    }),
    deleteJob: vi.fn(async (id: string) => {
      removed.push({ kind: "job", id });
    }),
  };
}

describe("sample cleanup", () => {
  it("plans children before parents", () => {
    const plan = planSampleRemoval(sampleRecordsForTour());

    const kinds = plan.map((record) => record.kind);
    expect(kinds.indexOf("evidence")).toBeLessThan(kinds.indexOf("job"));
    expect(kinds.indexOf("outcome")).toBeLessThan(kinds.indexOf("job"));
    expect(kinds.indexOf("step")).toBeLessThan(kinds.indexOf("job"));
  });

  it("de-duplicates a record that appears twice", () => {
    const plan = planSampleRemoval(sampleRecordsForTour(), sampleRecordsForTour());

    expect(plan).toHaveLength(sampleRecordsForTour().length);
  });

  it("only ever names sample ids, so a person's record can never match", () => {
    const canvas = {
      jobs: [{ id: SAMPLE_JOB_ID }, { id: "JOB-MINE" }],
      steps: [],
      outcomes: [{ id: SAMPLE_OUTCOME_ID }, { id: "O-MINE" }],
      evidence: [{ id: "E-MINE" }],
      source: "local" as const,
    } as unknown as CanvasData;

    const found = sampleRecordsIn(canvas).map((record) => record.id);
    expect(found).toContain(SAMPLE_JOB_ID);
    expect(found).toContain(SAMPLE_OUTCOME_ID);
    expect(found).not.toContain("JOB-MINE");
    expect(found).not.toContain("O-MINE");
    expect(found).not.toContain("E-MINE");
  });

  it("removes every sample record and reports the ids", async () => {
    const ops = actions();

    const removed = await removeSampleRecords(sampleRecordsForTour(), ops);

    expect(removed.sort()).toEqual(
      sampleRecordsForTour()
        .map((record) => record.id)
        .sort(),
    );
    expect(ops.removed).toHaveLength(sampleRecordsForTour().length);
  });

  it("does nothing when the canvas holds no sample records", async () => {
    const ops = actions();

    const removed = await removeSampleRecords(
      sampleRecordsIn({
        jobs: [{ id: "JOB-MINE" }],
        steps: [],
        outcomes: [],
        evidence: [],
        source: "local",
      }),
      ops,
    );

    expect(removed).toEqual([]);
    expect(ops.deleteJob).not.toHaveBeenCalled();
  });
});
