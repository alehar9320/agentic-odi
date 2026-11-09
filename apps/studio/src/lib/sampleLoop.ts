import type { Evidence, Job, Outcome } from "../types";
import { opportunityScore } from "./odi";

/**
 * The one sample brief the tour rehearses on.
 *
 * Data, not a store write. The fixture is a frozen singleton: it is built once,
 * never persisted, never merged into a real job, and every record carries
 * `source: "sample"` and `simulated: true` so any surface that shows it can
 * label it. The tour reads it; nothing writes it.
 */

export const SAMPLE_SOURCE = "sample" as const;

export type SampleProvenance = typeof SAMPLE_SOURCE;

export interface SampleJob extends Job {
  source: SampleProvenance;
  simulated: true;
}

export interface SampleQuote extends Evidence {
  source: SampleProvenance;
  simulated: true;
}

export interface SampleOutcome extends Omit<Outcome, "id"> {
  id: string;
  source: SampleProvenance;
  simulated: true;
}

/**
 * How a paraphrase of the quote relates to the job. The job is the progress the
 * person is after; a workaround is how they cope today, and a solution is a
 * product in disguise. Only the job reading is right, and the wrong ones are
 * named for what they are rather than just marked wrong.
 */
export type InterpretationKind = "job" | "workaround" | "solution";

export interface QuoteInterpretation {
  id: string;
  text: string;
  kind: InterpretationKind;
  /** Why this reading is the job, or what it names instead. */
  verdict: string;
}

export interface SampleLoop {
  job: SampleJob;
  /** The customer's words, with the source line that says they are a sample. */
  quote: SampleQuote;
  /** Statement only: the tour scores it, so no number is invented here. */
  outcome: SampleOutcome;
  /** The three paraphrases scene one asks the person to choose between. */
  interpretations: QuoteInterpretation[];
  /** The outcomes scene two's score sits beside, so it is not a lonely number. */
  comparisons: SampleOutcome[];
  /** What the loop is missing before it is evidence rather than an anecdote. */
  missingEvidence: string[];
  source: SampleProvenance;
  simulated: true;
}

const JOB_ID = "sample-job";
const QUOTE_ID = "sample-quote";
const OUTCOME_ID = "sample-outcome";
const COMPARISON_ROLLBACK_ID = "sample-outcome-rollback";
const COMPARISON_BLAME_ID = "sample-outcome-blame";

const JOB_STATEMENT = "Keep a service's configuration true from commit to production.";

/**
 * Scene one's three paraphrases. The job reading comes first; the workaround and
 * the solution are the two ways the quote is *not* read, and each says what it
 * actually names so a wrong pick teaches rather than scolds.
 */
const INTERPRETATIONS: QuoteInterpretation[] = [
  {
    id: "know-which-config-is-live",
    text: "Know which config is live before shipping.",
    kind: "job",
    verdict:
      "That is the job: the progress the speaker is after. It is inferred from the quote, not copied out of it.",
  },
  {
    id: "keep-a-spreadsheet",
    text: "Keep a spreadsheet of config keys.",
    kind: "workaround",
    verdict:
      "That is the current workaround, not the job. A spreadsheet is how the speaker copes today, not what they are trying to accomplish.",
  },
  {
    id: "stop-using-config-keys",
    text: "Stop using config keys.",
    kind: "solution",
    verdict:
      "That is a solution in disguise. \"Stop using config keys\" is a product decision; the job is the progress underneath it.",
  },
];

function deepFreeze<T>(value: T): T {
  if (value && typeof value === "object") {
    for (const child of Object.values(value as Record<string, unknown>)) {
      deepFreeze(child);
    }
    Object.freeze(value);
  }
  return value;
}

function buildSampleLoop(): SampleLoop {
  return deepFreeze({
    job: {
      id: JOB_ID,
      name: JOB_STATEMENT,
      description: "A sample job, for the tour only.",
      source: SAMPLE_SOURCE,
      simulated: true,
    },
    quote: {
      id: QUOTE_ID,
      job_id: JOB_ID,
      outcome_id: OUTCOME_ID,
      name: "Config keys drift between environments",
      content: "I keep a spreadsheet of config keys because I can't tell which ones are live.",
      source_name: "one onboarding call, sample",
      source_kind: "interview",
      item_type: "quote",
      source: SAMPLE_SOURCE,
      simulated: true,
    },
    outcome: {
      id: OUTCOME_ID,
      job_id: JOB_ID,
      statement:
        "Minimize the time it takes to confirm which config keys are live before a deploy.",
      importance: null,
      satisfaction: null,
      opportunity_score: null,
      source: SAMPLE_SOURCE,
      simulated: true,
    },
    interpretations: INTERPRETATIONS.map((entry) => ({ ...entry })),
    comparisons: [
      {
        id: COMPARISON_ROLLBACK_ID,
        job_id: JOB_ID,
        statement: "Minimize the time it takes to roll back a bad config change.",
        importance: 9,
        satisfaction: 8,
        opportunity_score: opportunityScore(9, 8),
        source: SAMPLE_SOURCE,
        simulated: true,
      },
      {
        id: COMPARISON_BLAME_ID,
        job_id: JOB_ID,
        statement: "Minimize the time it takes to find who changed a key.",
        importance: 8,
        satisfaction: 2,
        opportunity_score: opportunityScore(8, 2),
        source: SAMPLE_SOURCE,
        simulated: true,
      },
    ],
    missingEvidence: [
      "One customer only.",
      "No linked job step.",
      "No second source.",
    ],
    source: SAMPLE_SOURCE,
    simulated: true,
  } satisfies SampleLoop);
}

let cached: SampleLoop | null = null;

/**
 * The sample brief, built once. Restarting the tour never builds a second one,
 * so the sample cannot multiply into the store or into a count.
 */
export function sampleLoop(): SampleLoop {
  cached ??= buildSampleLoop();
  return cached;
}

/**
 * The sample outcome with the two ratings applied, scored by the real formula.
 * This is what scene two stores: the number is computed, never a literal, so it
 * cannot drift from the score the rest of the studio uses.
 */
export function scoreSampleOutcome(
  importance: number,
  satisfaction: number,
): SampleOutcome {
  return {
    ...sampleLoop().outcome,
    importance,
    satisfaction,
    opportunity_score: opportunityScore(importance, satisfaction),
  };
}
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

/** Every id this fixture created, so a cleanup deletes exactly these. */
export function sampleRecordIds(loop: SampleLoop = sampleLoop()): string[] {
  return [
    loop.job.id,
    loop.quote.id,
    loop.outcome.id,
    ...loop.comparisons.map((outcome) => outcome.id),
  ];
}

/** True only for a record this module made; a real record never answers true. */
export function isSampleRecord(record: { source?: string } | null | undefined): boolean {
  return record?.source === SAMPLE_SOURCE;
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
