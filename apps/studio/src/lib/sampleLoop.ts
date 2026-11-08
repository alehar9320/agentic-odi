import type { Evidence, Job, Outcome } from "../types";

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

export interface SampleLoop {
  job: SampleJob;
  /** The customer's words, with the source line that says they are a sample. */
  quote: SampleQuote;
  /** Statement only: the tour scores it, so no number is invented here. */
  outcome: SampleOutcome;
  /** What the loop is missing before it is evidence rather than an anecdote. */
  missingEvidence: string[];
  source: SampleProvenance;
  simulated: true;
}

const JOB_ID = "sample-job";
const QUOTE_ID = "sample-quote";
const OUTCOME_ID = "sample-outcome";

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
      name: "Keep a service's configuration true from commit to production.",
      description: "A sample job, for the tour only.",
      source: SAMPLE_SOURCE,
      simulated: true,
    },
    quote: {
      id: QUOTE_ID,
      job_id: JOB_ID,
      outcome_id: null,
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

/** Every id this fixture created, so a cleanup deletes exactly these. */
export function sampleRecordIds(loop: SampleLoop = sampleLoop()): string[] {
  return [loop.job.id, loop.quote.id, loop.outcome.id];
}

/** True only for a record this module made; a real record never answers true. */
export function isSampleRecord(record: { source?: string } | null | undefined): boolean {
  return record?.source === SAMPLE_SOURCE;
}
