import type { CanvasData, Evidence, Job, Outcome, Step } from "../types";

/**
 * The kinds the canvas actually carries. Thesis, Segment and Strategy are not
 * in `CanvasData`, so they are not listed here: a table cannot show what the
 * sidecar never sent.
 */
export type RecordKind = "job" | "step" | "outcome" | "evidence";

/** One stored record, flattened into the cells a table can render. */
export interface RecordRow {
  kind: RecordKind;
  /** Stable within one canvas; a record without an id still gets a row. */
  rowKey: string;
  id: string | null;
  /** The record this one belongs to, when it belongs to one. */
  parentId: string | null;
  cells: string[];
  /** The record itself, so opening a row never re-derives it from cells. */
  record: Job | Step | Outcome | Evidence;
}

export interface RecordSection {
  kind: RecordKind;
  label: string;
  columns: string[];
}

/** Past this many rows in one section the table says so instead of growing. */
export const MAX_ROWS = 200;

/** Every section ends with the id column, so the table can render it in mono. */
export const RECORD_SECTIONS: RecordSection[] = [
  { kind: "job", label: "Jobs", columns: ["Name", "Description", "Id"] },
  { kind: "step", label: "Steps", columns: ["Order", "Name", "Job", "Id"] },
  {
    kind: "outcome",
    label: "Desired outcomes",
    columns: ["Statement", "Importance", "Satisfaction", "Score", "Job", "Id"],
  },
  {
    kind: "evidence",
    label: "Evidence",
    columns: ["Source", "Kind", "Type", "Name", "Outcome", "Id"],
  },
];

/** A missing field says so; it never renders as `undefined`. */
function text(value: string | number | null | undefined): string {
  if (value === null || value === undefined) {
    return "—";
  }
  const rendered = String(value).trim();
  return rendered.length > 0 ? rendered : "—";
}

/** A score is the number the sidecar returned, or the word for having none. */
function score(value: number | null | undefined): string {
  return value === null || value === undefined ? "unscored" : String(value);
}

/**
 * Every record the canvas holds, in section order.
 *
 * Pure, and deliberately so: the numbers on this table are the numbers the
 * store returned. The one thing this never does is recompute an opportunity
 * score from importance and satisfaction, because a table the user reads as
 * "what is stored" must not quietly disagree with the store.
 */
export function buildRecords(canvas: CanvasData | null | undefined): RecordRow[] {
  if (!canvas) {
    return [];
  }

  const rows: RecordRow[] = [];

  canvas.jobs.forEach((job, index) => {
    rows.push({
      kind: "job",
      rowKey: `job:${job.id || index}`,
      id: job.id || null,
      parentId: null,
      cells: [text(job.name), text(job.description), text(job.id)],
      record: job,
    });
  });

  canvas.steps.forEach((step, index) => {
    rows.push({
      kind: "step",
      rowKey: `step:${step.id || index}`,
      id: step.id ?? null,
      parentId: step.job_id ?? null,
      cells: [text(step.order), text(step.name), text(step.job_id), text(step.id)],
      record: step,
    });
  });

  canvas.outcomes.forEach((outcome, index) => {
    rows.push({
      kind: "outcome",
      rowKey: `outcome:${outcome.id || index}`,
      id: outcome.id ?? null,
      parentId: outcome.job_id ?? null,
      cells: [
        text(outcome.statement),
        text(outcome.importance),
        text(outcome.satisfaction),
        score(outcome.opportunity_score),
        text(outcome.job_id),
        text(outcome.id),
      ],
      record: outcome,
    });
  });

  (canvas.evidence ?? []).forEach((evidence, index) => {
    rows.push({
      kind: "evidence",
      rowKey: `evidence:${evidence.id || index}`,
      id: evidence.id || null,
      parentId: evidence.outcome_id ?? evidence.step_id ?? evidence.job_id ?? null,
      cells: [
        text(evidence.source_name),
        text(evidence.source_kind),
        text(evidence.item_type),
        text(evidence.name),
        text(evidence.outcome_id),
        text(evidence.id),
      ],
      record: evidence,
    });
  });

  return rows;
}
