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
}
