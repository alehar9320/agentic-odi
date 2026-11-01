import type { CanvasData } from "../types";
import {
  SAMPLE_EVIDENCE_IDS,
  SAMPLE_JOB_ID,
  SAMPLE_OUTCOME_IDS,
  SAMPLE_STEP_ID,
} from "../lib/sampleLoop";

/**
 * Removing the sample brief.
 *
 * The plan is built from the fixed sample ids only, so a record a person made
 * can never be matched. Children are removed before parents.
 */

export type SampleRecordKind = "evidence" | "outcome" | "step" | "job";

export interface SampleRecord {
  kind: SampleRecordKind;
  id: string;
}

export interface SampleCleanupActions {
  deleteEvidence: (evidenceId: string) => Promise<void>;
  deleteOutcome: (outcomeId: string) => Promise<void>;
  deleteStep: (stepId: string) => Promise<void>;
  deleteJob: (jobId: string) => Promise<void>;
}

const SAMPLE_IDS: Record<SampleRecordKind, Set<string>> = {
  evidence: new Set<string>(SAMPLE_EVIDENCE_IDS),
  outcome: new Set<string>(SAMPLE_OUTCOME_IDS),
  step: new Set<string>([SAMPLE_STEP_ID]),
  job: new Set<string>([SAMPLE_JOB_ID]),
};

const KIND_ORDER: SampleRecordKind[] = ["evidence", "outcome", "step", "job"];

/** True when an id belongs to the tour's sample brief, never to a person's. */
export function isSampleId(kind: SampleRecordKind, id: string): boolean {
  return SAMPLE_IDS[kind].has(id);
}

/** The sample records a canvas holds. Anything else is left alone. */
export function sampleRecordsIn(canvas: CanvasData | null | undefined): SampleRecord[] {
  if (!canvas) {
    return [];
  }
  const records: SampleRecord[] = [];
  const collect = (
    kind: SampleRecordKind,
    items: Array<{ id?: string }> | undefined,
  ) => {
    for (const item of items ?? []) {
      if (item.id && isSampleId(kind, item.id)) {
        records.push({ kind, id: item.id });
      }
    }
  };
  collect("evidence", canvas.evidence);
  collect("outcome", canvas.outcomes);
  collect("step", canvas.steps);
  collect("job", canvas.jobs);
  return records;
}

/** Merge record lists into a de-duplicated, child-first removal plan. */
export function planSampleRemoval(...lists: SampleRecord[][]): SampleRecord[] {
  const seen = new Set<string>();
  const planned: SampleRecord[] = [];
  for (const kind of KIND_ORDER) {
    for (const list of lists) {
      for (const record of list) {
        if (record.kind !== kind) {
          continue;
        }
        const key = `${record.kind}:${record.id}`;
        if (seen.has(key)) {
          continue;
        }
        seen.add(key);
        planned.push(record);
      }
    }
  }
  return planned;
}

/**
 * Delete the planned sample records, children first. Returns the ids removed.
 * A record a person made is never in the plan, so it survives untouched.
 */
export async function removeSampleRecords(
  records: SampleRecord[],
  actions: SampleCleanupActions,
): Promise<string[]> {
  const removed: string[] = [];
  for (const record of planSampleRemoval(records)) {
    if (record.kind === "evidence") {
      await actions.deleteEvidence(record.id);
    } else if (record.kind === "outcome") {
      await actions.deleteOutcome(record.id);
    } else if (record.kind === "step") {
      await actions.deleteStep(record.id);
    } else {
      await actions.deleteJob(record.id);
    }
    removed.push(record.id);
  }
  return removed;
}
