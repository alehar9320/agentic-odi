import type { Outcome } from "../types";

/**
 * The tour's sample brief: one frozen, labelled dataset shared by the tour and
 * the empty state (#318). It is data, never a store write — nothing here reaches
 * IndexedDB, the canvas, a rail count, or a landscape total, and no sample
 * record is ever mixed into a real job.
 *
 * The outcome ships unscored: hearing the quote is the first slice (#593), and
 * scoring it is the second (#594).
 */

export const SAMPLE_JOB_ID = "sample-job";
export const SAMPLE_QUOTE_ID = "sample-quote";
export const SAMPLE_OUTCOME_ID = "sample-outcome";

export interface SampleQuote {
  id: string;
  text: string;
  /** Where it came from, named so the sample is never mistaken for a real call. */
  source: string;
}

export interface SampleBrief {
  /** The label every surface reads to say "sample". */
  source: "sample";
  simulated: true;
  job: { id: string; statement: string };
  quote: SampleQuote;
  outcome: Outcome;
  missing_evidence: string[];
}

function build(): SampleBrief {
  return Object.freeze({
    source: "sample",
    simulated: true,
    job: {
      id: SAMPLE_JOB_ID,
      statement: "Keep a service's configuration true from commit to production.",
    },
    quote: {
      id: SAMPLE_QUOTE_ID,
      text: "I keep a spreadsheet of config keys because I can't tell which ones are live.",
      source: "one onboarding call, sample",
    },
    outcome: {
      id: SAMPLE_OUTCOME_ID,
      job_id: SAMPLE_JOB_ID,
      statement:
        "Minimize the time it takes to confirm which config keys are live before a deploy.",
      importance: null,
      satisfaction: null,
      opportunity_score: null,
    },
    missing_evidence: ["One customer only", "No linked job step", "No second source"],
  });
}

let cached: SampleBrief | null = null;

/** The one sample brief, built on first use and reused forever after. */
export function sampleLoop(): SampleBrief {
  cached ??= build();
  return cached;
}

/** True only for a record this fixture produced, so a real one is never removed. */
export function isSampleRecord(record: { id?: string } | null | undefined): boolean {
  if (!record?.id) {
    return false;
  }
  return (
    record.id === SAMPLE_JOB_ID ||
    record.id === SAMPLE_QUOTE_ID ||
    record.id === SAMPLE_OUTCOME_ID
  );
}
