/**
 * `@` mentions: the canvas, as something the keyboard can name.
 *
 * The popover is fed from records the store already holds, never from a list
 * this module invents. A record without an id cannot be named — inserting
 * `@undefined` would tell the agent about something that does not exist — so it
 * is left out rather than guessed at.
 */

import type { DirectiveFormatter, TriggerItem } from "@assistant-ui/react";

import { formatOpportunityScore } from "../lib/odi";
import type { CanvasData, Evidence, Outcome, Step } from "../types";

export type MentionKind = "job" | "step" | "outcome" | "evidence";

export interface MentionItem {
  /** The record's own id, which is what a mention inserts. */
  id: string;
  kind: MentionKind;
  /** What the store calls the record. */
  label: string;
  /** The kind, and the record it belongs to, for the second line. */
  hint: string;
}

/** Past this many candidates the popover narrows with the query instead. */
export const MAX_MENTIONS = 50;

/** Kind order, also the tie-break when two records are equally recent. */
const KIND_ORDER: readonly MentionKind[] = ["job", "step", "outcome", "evidence"];

const KIND_LABEL: Record<MentionKind, string> = {
  job: "Job",
  step: "Step",
  outcome: "Outcome",
  evidence: "Evidence",
};

function trimmed(value: string | null | undefined): string {
  return typeof value === "string" ? value.trim() : "";
}

function jobNames(canvas: CanvasData): Map<string, string> {
  const names = new Map<string, string>();
  for (const job of canvas.jobs) {
    const name = trimmed(job.name);
    if (job.id && name) {
      names.set(job.id, name);
    }
  }
  return names;
}

function stepHint(step: Step, names: Map<string, string>): string {
  const job = step.job_id ? names.get(step.job_id) : undefined;
  return job ? `${KIND_LABEL.step} · ${job}` : KIND_LABEL.step;
}

function outcomeHint(outcome: Outcome, names: Map<string, string>): string {
  const job = outcome.job_id ? names.get(outcome.job_id) : undefined;
  const score =
    outcome.opportunity_score == null ? "" : ` · ${formatOpportunityScore(outcome.opportunity_score)}`;
  return job ? `${KIND_LABEL.outcome} · ${job}${score}` : `${KIND_LABEL.outcome}${score}`;
}

function evidenceLabel(evidence: Evidence): string {
  const named = trimmed(evidence.name);
  if (named) {
    return named;
  }
  const content = trimmed(evidence.content);
  return content ? content.slice(0, 60) : "Untitled evidence";
}

function evidenceHint(evidence: Evidence): string {
  const source = trimmed(evidence.source_name);
  return source ? `${KIND_LABEL.evidence} · ${source}` : KIND_LABEL.evidence;
}

/** One candidate, with the recency the ordering needs. */
interface Candidate extends MentionItem {
  /** Position in canvas order; a later position was created later. */
  recency: number;
}

/**
 * Every record the canvas can name, ordered for the popover.
 *
 * With a query the order is exact id match, then label starts-with, then
 * everything else; without one it is recency. Ties fall back to recency, then
 * to kind order, so the list is stable across renders.
 */
export function toMentionItems(canvas: CanvasData | null | undefined, query = ""): MentionItem[] {
  if (!canvas) {
    return [];
  }

  const names = jobNames(canvas);
  const candidates: Candidate[] = [];
  let recency = 0;

  const push = (kind: MentionKind, id: string, label: string, hint: string) => {
    candidates.push({ id, kind, label, hint, recency });
    recency += 1;
  };

  for (const job of canvas.jobs) {
    if (job.id) {
      push("job", job.id, trimmed(job.name) || "Untitled job", KIND_LABEL.job);
    }
  }
  for (const step of canvas.steps) {
    if (step.id) {
      push("step", step.id, trimmed(step.name) || "Untitled step", stepHint(step, names));
    }
  }
  for (const outcome of canvas.outcomes) {
    if (outcome.id) {
      push(
        "outcome",
        outcome.id,
        trimmed(outcome.statement) || "Untitled outcome",
        outcomeHint(outcome, names),
      );
    }
  }
  for (const evidence of canvas.evidence ?? []) {
    if (evidence.id) {
      push("evidence", evidence.id, evidenceLabel(evidence), evidenceHint(evidence));
    }
  }

  const needle = query.trim().toLowerCase();
  const score = (candidate: Candidate): number => {
    if (!needle) {
      return 0;
    }
    if (candidate.id.toLowerCase() === needle) {
      return 0;
    }
    if (candidate.label.toLowerCase().startsWith(needle)) {
      return 1;
    }
    return 2;
  };

  return candidates
    .sort((a, b) => {
      const byScore = score(a) - score(b);
      if (byScore !== 0) {
        return byScore;
      }
      const byRecency = b.recency - a.recency;
      if (byRecency !== 0) {
        return byRecency;
      }
      return KIND_ORDER.indexOf(a.kind) - KIND_ORDER.indexOf(b.kind);
    })
    .slice(0, MAX_MENTIONS)
    .map(({ id, kind, label, hint }) => ({ id, kind, label, hint }));
}

/**
 * Serialize a chosen mention as the literal `@<id>`.
 *
 * The id, never the statement: a statement is long, and inserting it would put
 * words in the person's mouth that they did not type. The agent resolves the id
 * or says it does not know it — the client never invents a record.
 */
export const mentionFormatter: DirectiveFormatter = {
  serialize: (item: TriggerItem) => `@${item.id}`,
  // The Studio sends the typed text as-is, so nothing is ever re-parsed into a
  // chip: everything is literal.
  parse: (text: string) => (text ? [{ kind: "text", text }] : []),
};
