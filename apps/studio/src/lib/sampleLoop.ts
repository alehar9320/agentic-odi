import type { CanvasData, Evidence, Job, Outcome, Step } from "../types";
import { opportunityScore } from "./odi";

/**
 * The one sample brief the tour rehearses, as data.
 *
 * It is never written to IndexedDB and never enters the real canvas. The tour
 * renders it from here, so every sample record is identifiable by its id and
 * can be removed without touching anything a person made.
 */

export const SAMPLE_SOURCE = "sample";

export const SAMPLE_JOB_ID = "SAMPLE-JOB";
export const SAMPLE_STEP_ID = "SAMPLE-STEP";
export const SAMPLE_EVIDENCE_ID = "SAMPLE-E1";

/** The outcome scene two scores and scene three lands. */
export const SAMPLE_OUTCOME_ID = "SAMPLE-O1";
export const SAMPLE_COMPARISON_IDS = ["SAMPLE-O2", "SAMPLE-O3"] as const;

export const SAMPLE_JOB_NAME =
  "Keep a service's configuration true from commit to production.";

export const SAMPLE_QUOTE =
  "I keep a spreadsheet of config keys because I can't tell which ones are live.";
export const SAMPLE_QUOTE_SOURCE = "one onboarding call, sample.";

/** Everything the tour creates, so cleanup can delete exactly this and no more. */
export const SAMPLE_OUTCOME_IDS = [
  SAMPLE_OUTCOME_ID,
  ...SAMPLE_COMPARISON_IDS,
] as const;
export const SAMPLE_EVIDENCE_IDS = [SAMPLE_EVIDENCE_ID] as const;

export const SAMPLE_JOB: Job = {
  id: SAMPLE_JOB_ID,
  name: SAMPLE_JOB_NAME,
  description: "Sample brief. Nothing here comes from your research.",
};

export const SAMPLE_STEP: Step = {
  id: SAMPLE_STEP_ID,
  job_id: SAMPLE_JOB_ID,
  name: "Confirm the config before a deploy",
  order: 1,
};

export const SAMPLE_EVIDENCE: Evidence = {
  id: SAMPLE_EVIDENCE_ID,
  source_name: SAMPLE_QUOTE_SOURCE,
  source_kind: SAMPLE_SOURCE,
  item_type: "quote",
  content: SAMPLE_QUOTE,
  job_id: SAMPLE_JOB_ID,
  step_id: SAMPLE_STEP_ID,
  outcome_id: SAMPLE_OUTCOME_ID,
};

function outcome(
  id: string,
  statement: string,
  importance: number,
  satisfaction: number,
): Outcome {
  return {
    id,
    job_id: SAMPLE_JOB_ID,
    statement,
    importance,
    satisfaction,
    opportunity_score: opportunityScore(importance, satisfaction),
  };
}

/** The scored outcome scene three highlights, and the two it is compared to. */
export const SAMPLE_OUTCOMES: Outcome[] = [
  outcome(
    SAMPLE_OUTCOME_ID,
    "Minimize the time it takes to confirm which config keys are live before a deploy.",
    9,
    3,
  ),
  outcome(
    SAMPLE_COMPARISON_IDS[0],
    "Minimize the time it takes to roll back a bad config change.",
    9,
    8,
  ),
  outcome(
    SAMPLE_COMPARISON_IDS[1],
    "Minimize the time it takes to find who changed a key.",
    8,
    2,
  ),
];

/** What the sample does not yet prove. The tour names it rather than hiding it. */
export const SAMPLE_MISSING_EVIDENCE = [
  "One customer only.",
  "No linked job step.",
  "No second source.",
] as const;

/** The sample brief as a canvas the plot can render, marked as sample data. */
export function sampleCanvas(): CanvasData {
  return {
    jobs: [{ ...SAMPLE_JOB }],
    steps: [{ ...SAMPLE_STEP }],
    outcomes: SAMPLE_OUTCOMES.map((item) => ({ ...item })),
    evidence: [{ ...SAMPLE_EVIDENCE }],
    source: "seed",
  };
}

/**
 * Every record the tour created, as (kind, id) pairs. This is the exact set the
 * exit choice may remove — nothing else can be in it, so no record a person
 * made can ever be matched by the cleanup.
 */
export function sampleRecordsForTour(): Array<{
  kind: "evidence" | "outcome" | "step" | "job";
  id: string;
}> {
  return [
    { kind: "evidence", id: SAMPLE_EVIDENCE_ID },
    ...SAMPLE_OUTCOME_IDS.map((id) => ({ kind: "outcome" as const, id })),
    { kind: "step", id: SAMPLE_STEP_ID },
    { kind: "job", id: SAMPLE_JOB_ID },
  ];
}
