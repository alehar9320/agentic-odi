/**
 * The answered half of the interview card (issue #400).
 *
 * An interview that has been saved collapses into one line naming what it
 * produced; one that is still being answered stays live. The counts in that
 * line are read from the records the store actually created, never from how
 * many questions were answered — a question that produced nothing must read
 * `0 outcomes`, not a number the card made up.
 *
 * Pure and renderer-free: the mapping from a saved interview to the words and
 * the links on screen is one function a test can pin.
 */

import type { Answers } from "../../assistant/interview/conductor";

/** What the submit path actually created, as counts and as ids. */
export interface CreatedRecords {
  /** The id of each outcome the store confirmed, in creation order. */
  outcomeIds: string[];
  /** How many evidence records the store confirmed. */
  evidenceCount: number;
}

export interface AnsweredInterview {
  /** The questions that were asked, in order, so the record can replay them. */
  questions: { id: string; prompt: string }[];
  /** The answers the person gave, keyed by question id. */
  answers: Answers;
  /** The records the answers produced. */
  created: CreatedRecords;
}

/** The noun for a count: singular at one, plural otherwise. */
export function plural(count: number, singular: string, pluralForm: string): string {
  return count === 1 ? singular : pluralForm;
}

function isAnswered(value: string | number | undefined | null): boolean {
  if (value === undefined || value === null) {
    return false;
  }
  return typeof value === "number" ? true : value.trim() !== "";
}

/**
 * The one summary line: `Answered · 3 of 3 · 2 outcomes, 1 evidence`.
 *
 * The first pair counts the questions that were answered, not the records; the
 * second pair counts the records the store confirmed. A submission that wrote
 * nothing reads `0 outcomes, 0 evidence` rather than the number of answers.
 */
export function answeredSummaryLine(answered: AnsweredInterview): string {
  const asked = answered.questions.length;
  const given = answered.questions.filter((question) =>
    isAnswered(answered.answers[question.id]),
  ).length;
  const outcomes = answered.created.outcomeIds.length;
  const evidence = answered.created.evidenceCount;
  return (
    `Answered · ${given} of ${asked} · ` +
    `${outcomes} ${plural(outcomes, "outcome", "outcomes")}, ` +
    `${evidence} ${plural(evidence, "evidence", "evidence")}`
  );
}

/** One created outcome the record links through the existing focus action. */
export interface RecordLink {
  id: string;
  label: string;
}

/**
 * The links the answered record offers: one per outcome the store created, in
 * creation order. Evidence carries no id back from its write today, so it is
 * counted in the summary and never given a link that would name nothing.
 */
export function recordLinks(created: CreatedRecords): RecordLink[] {
  return created.outcomeIds.map((id, index) => ({ id, label: `Outcome ${index + 1}` }));
}

/** The line a failed submission shows instead of a summary. */
export function notSavedLine(reason: string): string {
  const trimmed = reason.trim();
  return trimmed ? `Not saved — ${trimmed}` : "Not saved — the write did not complete.";
}
