/**
 * The decision brief: one document a reviewer can read without the app.
 *
 * Everything here is assembled from records the studio already holds — the
 * canvas, the setup brief, and the theses saved against outcomes. The generator
 * states its sources and never invents prose: an empty section says so.
 *
 * It runs client-side from `StudioContext` state so a brief can be produced with
 * the sidecar down, from the same rows the lenses are drawing.
 */

import type {
  CanvasData,
  CanvasProvenance,
  ConnectorPreset,
  StudioBrief,
  Thesis,
} from "../types";
import { isSimulatedCanvas } from "./canvasProvenance";

/** Excerpts are quoted, not reproduced: two lines is enough to recognise a signal. */
export const EXCERPT_LIMIT = 240;

/** The brief is two pages, so it ranks the top five and quotes three records each. */
export const OPPORTUNITY_LIMIT = 5;
export const EVIDENCE_PER_OUTCOME = 3;

export const SCORE_FORMULA = "importance + max(importance - satisfaction, 0)";

export const SEED_WATERMARK = "Demo data. Nothing here comes from your research.";

export interface BriefOpportunity {
  id: string;
  statement: string;
  importance: number | null;
  satisfaction: number | null;
  score: number | null;
  /** Live records linked to this outcome by `outcome_id`. */
  evidence_count: number;
}

export interface BriefEvidence {
  id: string;
  outcome_id: string;
  source_name: string;
  item_type: string;
  name: string;
  excerpt: string;
  truncated: boolean;
  url: string | null;
}

export type DissentSource = "thesis" | "warning" | "unlinked-evidence" | "author";

export interface BriefDissentEntry {
  text: string;
  source: DissentSource;
  outcome_id?: string;
  /** The outcome the reasoning was saved against is no longer on the canvas. */
  stale?: boolean;
}

export interface BriefPreset {
  id: string;
  label: string;
  summary: string;
}

export interface BriefNextEvidence {
  outcome_id: string;
  statement: string;
  evidence_count: number;
  /** The capability area the gap points at, from the connector catalog. */
  area: string;
  presets: BriefPreset[];
  needs_connection: boolean;
}

export interface BriefProvenance {
  kind: "live" | "seed" | "empty";
  source: CanvasData["source"] | null;
  /** True when the rows came from the cache on this device, not from the sidecar. */
  cached: boolean;
  sample: boolean;
  /** Rows dropped because they were sample data, so no count below includes them. */
  excluded_sample_rows: { outcomes: number; evidence: number };
  /** The rows the brief actually counted, sample rows already removed. */
  counted_rows: { outcomes: number; evidence: number };
  record_counts: CanvasProvenance["record_counts"] | null;
  canvas_generated_at: string | null;
}

export interface BriefDecision {
  id: string;
  statement: string;
  score: number | null;
  rationale: string | null;
}

export interface DecisionBrief {
  schema_version: 1;
  generated_at: string;
  product_name: string;
  vision: string | null;
  decision: BriefDecision | null;
  opportunities: BriefOpportunity[];
  evidence: BriefEvidence[];
  unlinked_evidence_count: number;
  dissent: BriefDissentEntry[];
  next_evidence: BriefNextEvidence | null;
  provenance: BriefProvenance;
}

export interface DecisionBriefInput {
  canvas: CanvasData | null;
  brief: StudioBrief | null;
  theses: Thesis[];
  /** The connector catalog, when the sidecar answered; `[]` is a valid answer. */
  presets: ConnectorPreset[];
  canvasCached?: boolean;
  /** The one objection the author types on the export sheet. */
  authorObjection?: string;
  generatedAt?: Date;
}

function text(value: string | null | undefined): string {
  const trimmed = value?.trim();
  return trimmed ? trimmed : "";
}

function excerpt(content: string | undefined): { text: string; truncated: boolean } {
  const body = text(content ?? "").replace(/\s+/g, " ");
  if (body.length <= EXCERPT_LIMIT) {
    return { text: body, truncated: false };
  }
  return { text: body.slice(0, EXCERPT_LIMIT), truncated: true };
}

/**
 * The opportunity score is the core's, not a second opinion: `importance +
 * max(importance - satisfaction, 0)`. Outcomes without both ratings cannot be
 * ranked, so they are left out rather than given a score of zero.
 */
function scored(outcomes: CanvasData["outcomes"]): CanvasData["outcomes"] {
  return outcomes
    .filter((outcome) => outcome.opportunity_score != null)
    .sort((a, b) => (b.opportunity_score ?? 0) - (a.opportunity_score ?? 0));
}

export function buildDecisionBrief(input: DecisionBriefInput): DecisionBrief {
  const { canvas, brief, theses, presets, canvasCached = false, authorObjection } = input;
  const generatedAt = input.generatedAt ?? new Date();

  // Sample rows are never counted. The watermark says why the sections are empty.
  const sample = isSimulatedCanvas(canvas);
  const rows = sample ? [] : canvas?.outcomes ?? [];
  const records = sample ? [] : canvas?.evidence ?? [];
  const excluded_sample_rows = sample
    ? {
        outcomes: canvas?.outcomes.length ?? 0,
        evidence: canvas?.evidence?.length ?? 0,
      }
    : { outcomes: 0, evidence: 0 };

  const linkedCount = (outcomeId: string | undefined): number =>
    outcomeId ? records.filter((item) => item.outcome_id === outcomeId).length : 0;

  const ranked = scored(rows);
  const opportunities: BriefOpportunity[] = ranked.slice(0, OPPORTUNITY_LIMIT).map((outcome) => ({
    id: outcome.id ?? "",
    statement: text(outcome.statement ?? ""),
    importance: outcome.importance ?? null,
    satisfaction: outcome.satisfaction ?? null,
    score: outcome.opportunity_score ?? null,
    evidence_count: linkedCount(outcome.id),
  }));

  const topIds = new Set(opportunities.map((entry) => entry.id));
  const onCanvas = new Set(rows.map((outcome) => outcome.id ?? ""));
  const decisionOutcome = ranked[0];
  const decision: BriefDecision | null = opportunities[0]
    ? {
        id: opportunities[0].id,
        statement: opportunities[0].statement,
        score: opportunities[0].score,
        rationale:
          text(theses.find((item) => item.outcome_id === decisionOutcome?.id)?.rationale ?? "") ||
          null,
      }
    : null;

  const evidence: BriefEvidence[] = [];
  for (const entry of opportunities) {
    const linked = records.filter((item) => item.outcome_id === entry.id);
    for (const record of linked.slice(0, EVIDENCE_PER_OUTCOME)) {
      const quoted = excerpt(record.content);
      evidence.push({
        id: record.id,
        outcome_id: entry.id,
        source_name: text(record.source_name ?? "") || "Unknown source",
        item_type: text(record.item_type ?? "") || "record",
        name: text(record.name ?? "") || record.id,
        excerpt: quoted.text,
        truncated: quoted.truncated,
        url: record.url ?? null,
      });
    }
  }

  const unlinked_evidence_count = records.filter((item) => !item.outcome_id).length;

  const dissent: BriefDissentEntry[] = [];
  for (const saved of theses) {
    const rationale = text(saved.rationale);
    if (!rationale) {
      continue;
    }
    // The decision already carries its own rationale; repeating it two sections
    // down would look like a defect, not a counter-argument.
    if (topIds.has(saved.outcome_id) && saved.outcome_id !== decision?.id) {
      dissent.push({ text: rationale, source: "thesis", outcome_id: saved.outcome_id });
    } else if (!onCanvas.has(saved.outcome_id)) {
      dissent.push({
        text: rationale,
        source: "thesis",
        outcome_id: saved.outcome_id,
        stale: true,
      });
    }
  }
  for (const warning of canvas?.warnings ?? []) {
    const line = text(warning);
    if (line) {
      dissent.push({ text: line, source: "warning" });
    }
  }
  if (unlinked_evidence_count > 0) {
    dissent.push({
      text:
        unlinked_evidence_count === 1
          ? "1 captured record is not linked to any outcome."
          : `${unlinked_evidence_count} captured records are not linked to any outcome.`,
      source: "unlinked-evidence",
    });
  }
  const objection = text(authorObjection ?? "");
  if (objection) {
    dissent.push({ text: objection, source: "author" });
  }

  const next_evidence = buildNextEvidence(opportunities, rows, presets);

  const kind: BriefProvenance["kind"] = sample
    ? "seed"
    : !canvas || (canvas.jobs.length === 0 && canvas.steps.length === 0 && rows.length === 0)
      ? "empty"
      : "live";

  return {
    schema_version: 1,
    generated_at: generatedAt.toISOString(),
    product_name: text(brief?.product_name ?? "") || "Untitled product",
    vision: text(brief?.v2mom?.vision ?? "") || null,
    decision,
    opportunities,
    evidence,
    unlinked_evidence_count,
    dissent,
    next_evidence,
    provenance: {
      kind,
      source: canvas?.source ?? null,
      cached: canvasCached,
      sample,
      excluded_sample_rows,
      counted_rows: { outcomes: rows.length, evidence: records.length },
      record_counts: canvas?.provenance?.record_counts ?? null,
      canvas_generated_at: canvas?.provenance?.generated_at ?? null,
    },
  };
}

/**
 * The thinnest of the top three is the bet most likely to fall over, so that is
 * the one the brief says to go and evidence. An outcome that has quotes but no
 * measurements points at the quantitative sources; one with nothing points at
 * the customer.
 */
function buildNextEvidence(
  opportunities: BriefOpportunity[],
  rows: CanvasData["outcomes"],
  presets: ConnectorPreset[],
): BriefNextEvidence | null {
  const candidate = [...opportunities.slice(0, 3)].sort(
    (a, b) => a.evidence_count - b.evidence_count || (b.score ?? 0) - (a.score ?? 0),
  )[0];
  if (!candidate) {
    return null;
  }

  const outcome = rows.find((item) => item.id === candidate.id);
  const area =
    candidate.evidence_count > 0 && !text(outcome?.telemetry ?? "")
      ? "quantitative-data"
      : "voice-of-customer";

  const matches = presets
    .filter((item) => item.area === area)
    .sort((a, b) => Number(b.is_recommended) - Number(a.is_recommended))
    .slice(0, 2);

  return {
    outcome_id: candidate.id,
    statement: candidate.statement,
    evidence_count: candidate.evidence_count,
    area,
    presets: matches.map((item) => ({
      id: item.id,
      label: item.label,
      summary: item.summary,
    })),
    needs_connection: matches.length === 0,
  };
}
