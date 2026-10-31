/**
 * The closed catalog of surfaces the agent may compose.
 *
 * Two tiers, deliberately small: primitives for composition, cards for the ODI
 * shapes worth naming. Cards are leaves on the wire but render internally with
 * the same primitives, so the agent expresses intent ("score this outcome")
 * rather than layout.
 *
 * This file is the single source of truth. `catalogManifest()` is what travels
 * to the sidecar; `catalogPrompt()` is what the model reads.
 */

import { JOB_STAGES } from "../domain/jobStages";
import { UI_LIMITS, toManifest, type UiCatalogEntry, type UiPropSchema } from "./protocol";

const actionList: UiPropSchema = {
  type: "array",
  maxItems: UI_LIMITS.maxActions,
  description:
    "Buttons rendered under the surface. Each one sends its `intent` back to you as the user's next message.",
  items: {
    type: "object",
    properties: {
      label: {
        type: "string",
        description: "Short imperative label, two to four words. e.g. \"Simulate this bet\"",
      },
      intent: {
        type: "string",
        description: "The full message to send when clicked, written as the user would say it.",
      },
      tone: { enum: ["primary", "ghost"], description: "Use primary at most once per surface." },
    },
    required: ["label", "intent"],
  },
};

const outcomeScores: Record<string, UiPropSchema> = {
  importance: { type: "number", minimum: 0, maximum: 10 },
  satisfaction: { type: "number", minimum: 0, maximum: 10 },
};

const OPPORTUNITY_TONE: UiPropSchema = {
  enum: ["neutral", "positive", "warning", "critical"],
};

function entry(
  type: string,
  kind: UiCatalogEntry["kind"],
  description: string,
  properties: Record<string, UiPropSchema>,
  required: string[],
  options: { children?: boolean; actions?: boolean } = {},
): UiCatalogEntry {
  const props: Record<string, UiPropSchema> = { ...properties };
  if (options.actions !== false) {
    props.actions = actionList;
  }
  return {
    type,
    kind,
    description,
    acceptsChildren: options.children === true,
    props: {
      type: "object",
      properties: props,
      required,
    },
  };
}

export const CATALOG: readonly UiCatalogEntry[] = [
  // ---------------------------------------------------------------- primitives
  entry(
    "stack",
    "layout",
    "Vertical or horizontal grouping. The default container for anything that is not a card.",
    {
      direction: { enum: ["vertical", "horizontal"], description: "Defaults to vertical." },
      gap: { enum: ["sm", "md", "lg"], description: "Space between children. Defaults to md." },
    },
    [],
    { children: true },
  ),
  entry(
    "grid",
    "layout",
    "Two or three equal columns for parallel ideas — options, before/after, comparable outcomes.",
    {
      columns: { type: "integer", minimum: 2, maximum: 3, description: "How many columns." },
      gap: { enum: ["sm", "md", "lg"] },
    },
    ["columns"],
    { children: true, actions: false },
  ),
  entry(
    "heading",
    "leaf",
    "A section heading. Use sparingly — at most one per reply.",
    {
      text: { type: "string" },
      level: { type: "integer", minimum: 2, maximum: 3, description: "2 for a section, 3 for a sub." },
    },
    ["text"],
    { actions: false },
  ),
  entry(
    "text",
    "leaf",
    "A block of prose. Keep it to one or two sentences; cards carry the evidence.",
    {
      text: { type: "string", description: "Plain text. Inline **bold**, *italic* and `code` are supported." },
      tone: { enum: ["default", "muted", "positive", "warning", "critical"] },
    },
    ["text"],
    { actions: false },
  ),
  entry(
    "list",
    "leaf",
    "A short bulleted or numbered list. Use for steps and enumerations, not for evidence.",
    {
      items: { type: "array", minItems: 1, maxItems: 10, items: { type: "string" } },
      marker: { enum: ["dot", "number", "check"] },
    },
    ["items"],
    { actions: false },
  ),
  entry(
    "stat",
    "leaf",
    "A single headline number with its label and an optional delta.",
    {
      label: { type: "string" },
      value: { type: "string", description: "Pre-formatted, e.g. \"-90%\" or \"8.9 / 10\"." },
      delta: { type: "string", description: "Small supporting line, e.g. \"Friction eliminated\"." },
      tone: OPPORTUNITY_TONE,
    },
    ["label", "value"],
    { actions: false },
  ),
  entry(
    "meter",
    "leaf",
    "A labelled 0–10 bar. Use to make an importance or satisfaction rating visible.",
    {
      label: { type: "string" },
      value: { type: "number", minimum: 0, maximum: 10 },
      max: { type: "number", minimum: 1, maximum: 10, description: "Defaults to 10." },
      tone: OPPORTUNITY_TONE,
    },
    ["label", "value"],
    { actions: false },
  ),
  entry(
    "callout",
    "leaf",
    "A bordered note that demands attention: a risk, a verdict, a piece of guidance.",
    {
      tone: { enum: ["info", "positive", "warning", "critical"] },
      title: { type: "string" },
      body: { type: "string" },
    },
    ["tone", "body"],
    { actions: false },
  ),
  entry("divider", "leaf", "A thin rule between sections.", {}, [], { actions: false }),

  // --------------------------------------------------------------------- cards
  entry(
    "outcome-card",
    "leaf",
    "One desired outcome with its ODI scores and opportunity score. Your default answer when discussing a single outcome.",
    {
      id: { type: "string", description: "e.g. \"O-1\"." },
      statement: {
        type: "string",
        description: "The outcome in strict ODI form: direction + unit + object + context.",
      },
      ...outcomeScores,
      opportunityScore: {
        type: "number",
        minimum: 0,
        maximum: 20,
        description: "Omit it — the score is computed from importance and satisfaction.",
      },
      evidence: { type: "string", description: "The customer voice behind the rating." },
      sample: {
        type: "boolean",
        description: "True when this is bundled sample data rather than the user's own.",
      },
    },
    ["id", "statement", "importance", "satisfaction"],
  ),
  entry(
    "opportunity-board",
    "leaf",
    "A ranked table of outcomes by opportunity score. Use when comparing several needs at once.",
    {
      title: { type: "string" },
      outcomes: {
        type: "array",
        minItems: 1,
        maxItems: 12,
        items: {
          type: "object",
          properties: {
            id: { type: "string" },
            statement: { type: "string" },
            ...outcomeScores,
            opportunityScore: { type: "number", minimum: 0, maximum: 20 },
          },
          required: ["id", "statement", "importance", "satisfaction"],
        },
      },
    },
    ["outcomes"],
  ),
  entry(
    "impact-simulation",
    "leaf",
    "A before/after simulation of a proposed bet against one outcome. This is the WYSIWYG of human impact.",
    {
      outcome: {
        type: "object",
        properties: { id: { type: "string" }, statement: { type: "string" } },
        required: ["id", "statement"],
      },
      bet: { type: "string", description: "The product bet being tested, in plain words." },
      before: {
        type: "array",
        minItems: 1,
        maxItems: 6,
        items: { type: "string" },
        description: "Today's reality, concrete and measured.",
      },
      after: {
        type: "array",
        minItems: 1,
        maxItems: 6,
        items: { type: "string" },
        description: "The world with the bet shipped, equally concrete.",
      },
      metrics: {
        type: "array",
        maxItems: 4,
        items: {
          type: "object",
          properties: {
            label: { type: "string" },
            value: { type: "string" },
            delta: { type: "string" },
          },
          required: ["label", "value"],
        },
      },
      verdict: { type: "string", description: "One sentence: build it, reshape it, or drop it." },
      provenance: {
        enum: ["simulated"],
        description:
          "Must be `simulated`: no computation backs these numbers yet. Never present them as measurements.",
      },
    },
    ["outcome", "bet", "before", "after", "provenance"],
  ),
  entry(
    "evidence-quote",
    "leaf",
    "A verbatim customer signal with its source and lineage. Use instead of paraphrasing research.",
    {
      source: { type: "string", description: "Where it came from, e.g. \"Gong call #104 — FinTech Corp\"." },
      quote: { type: "string", description: "Exact words. Never paraphrase inside this field." },
      linkedTo: { type: "string", description: "The job or outcome it supports, e.g. \"JOB-402 / O-1\"." },
      severity: { enum: ["low", "medium", "high", "critical"] },
    },
    ["source", "quote"],
  ),
  entry(
    "job-map",
    "leaf",
    "The eight universal job stages for one job, in order. Use to show where in the process friction lives.",
    {
      job: { type: "string" },
      steps: {
        type: "array",
        minItems: 1,
        maxItems: JOB_STAGES.length,
        items: {
          type: "object",
          properties: {
            name: { type: "string" },
            stage: { enum: JOB_STAGES.map((stage) => stage.id) },
            note: { type: "string" },
          },
          required: ["name"],
        },
      },
    },
    ["job", "steps"],
  ),
  entry(
    "opportunity-thesis",
    "leaf",
    "One opportunity argued in plain language: the scores, the gap, the thesis, and the next move. Use when the PM is deciding what to chase.",
    {
      title: { type: "string", description: "The opportunity named as an outcome, not a feature." },
      ...outcomeScores,
      gap: { type: "string", description: "The customer or business gap in one sentence." },
      thesis: {
        type: "string",
        description: "Why this is the opportunity worth winning, in plain words. No framework jargon.",
      },
      next_move: { type: "string", description: "The smallest concrete step that would test it." },
    },
    ["title", "importance", "satisfaction", "thesis"],
  ),
  entry(
    "decision-record",
    "leaf",
    "A Product Decision Record: the bet, the outcome it serves, and why it was chosen.",
    {
      title: { type: "string" },
      outcomeId: { type: "string" },
      bet: { type: "string" },
      rationale: { type: "string" },
      status: { enum: ["proposed", "approved", "rejected"] },
    },
    ["title", "bet", "rationale"],
  ),
  entry(
    "decision-memo",
    "leaf",
    "The one-page decision memo, ready to leave the app. Shows the same markdown `odi decide memo` renders and offers one download. The file is written from the payload alone, so it carries no live view; a missing measurement is `not measured`, never a zero. Render it once, then one sentence — never restate in prose what the card shows.",
    {
      title: { type: "string" },
      markdown: {
        type: "string",
        description: "The memo body, exactly as the projection rendered it.",
      },
      html: {
        type: "string",
        description:
          "The standalone printable document, when the server rendered one. The download uses this; the card still shows the markdown.",
      },
      source: {
        type: "string",
        description: "What the export names as its origin, e.g. \"decision DEC-1\".",
      },
      generated_at: {
        type: "string",
        description: "Supplied export timestamp; the client never reads its own clock.",
      },
      schema_version: {
        type: "integer",
        minimum: 0,
        description: "The store's schema version stamped on the export.",
      },
      filename: {
        type: "string",
        description: "Suggested download filename. Defaults to the decision id.",
      },
      drafted: {
        type: "boolean",
        description: "True when a labelled, model-written framing block is included.",
      },
    },
    ["markdown"],
  ),
  entry(
    "outcome-compare",
    "leaf",
    "Two or three outcomes on the same axes, one row per metric and one column per outcome, so a choice is visible instead of argued. Use when comparing bets; never name a winner.",
    {
      title: { type: "string" },
      columns: {
        type: "array",
        minItems: 2,
        maxItems: 3,
        description: "One entry per outcome, in the order they should read. Ids are opaque labels.",
        items: { type: "string" },
      },
      rows: {
        type: "array",
        minItems: 1,
        items: {
          type: "object",
          properties: {
            metric: { type: "string", description: "The axis, e.g. \"score\" or \"sample_size\"." },
            label: { type: "string", description: "The human-readable axis name." },
            cells: {
              type: "array",
              items: {
                type: "string",
                description: "One cell per column. A missing measurement is the literal \"not measured\".",
              },
            },
          },
          required: ["label", "cells"],
        },
      },
    },
    ["columns", "rows"],
  ),
  entry(
    "opportunity-brief",
    "leaf",
    "The factual review case for one job: the decision, the underserved outcomes with their score, band, sample and quote, and the sources. Render it once, then one sentence — never describe in prose what the card shows.",
    {
      title: { type: "string" },
      job: { type: "string", description: "The job-to-be-done the case is for." },
      decision: {
        type: "string",
        description: "The decision being considered. Omit it when none is recorded.",
      },
      outcomes: {
        type: "array",
        minItems: 0,
        maxItems: 12,
        items: {
          type: "object",
          properties: {
            statement: { type: "string" },
            score: { type: "number", minimum: 0, maximum: 20 },
            band: { enum: ["underserved", "appropriate", "overserved", "unscored"] },
            n: { type: "integer", minimum: 0, description: "Sample size, when measured." },
            method: { type: "string", description: "How the score was measured." },
            quote: { type: "string", description: "A verbatim customer signal, when captured." },
            source: { type: "string", description: "Where the measurement came from." },
          },
          required: ["statement"],
        },
      },
      evidence_count: { type: "integer", minimum: 0 },
      generated_at: {
        type: "string",
        description: "Supplied generation timestamp; the client never reads its own clock.",
      },
    },
    ["title", "job", "outcomes"],
  ),
  entry(
    "roadmap",
    "leaf",
    "The outcome roadmap derived from recorded decisions: one row per chosen outcome, grouped by the quarter of its decision date. Shows the excluded count and why. Render it once, then one sentence — never restate in prose what the card shows.",
    {
      title: { type: "string" },
      entries: {
        type: "array",
        minItems: 0,
        maxItems: 40,
        items: {
          type: "object",
          properties: {
            period: { type: "string", description: "The quarter, e.g. \"2026-Q4\"." },
            outcome_id: { type: "string" },
            statement: { type: "string", description: "The outcome statement, not a feature name." },
            decision_id: { type: "string", description: "The decision this row traces back to." },
            baseline: {
              type: "number",
              description:
                "The measurement at decision time. Omit it when nobody measured one; the card shows \"not measured\".",
            },
            target: {
              type: "number",
              description:
                "The number we intend to reach. Omit it when nobody set one; the card shows \"not measured\".",
            },
          },
          required: ["period", "statement", "decision_id"],
        },
      },
      undecided_count: {
        type: "integer",
        minimum: 0,
        description: "Outcomes with no decision, excluded from the roadmap.",
      },
      horizon_excluded_count: { type: "integer", minimum: 0 },
      superseded_excluded_count: { type: "integer", minimum: 0 },
      exclusion_note: {
        type: "string",
        description: "One line naming what was left out and why. Always present.",
      },
    },
    ["entries", "exclusion_note"],
  ),
  entry(
    "decision-review",
    "leaf",
    "A past decision re-examined against today's numbers: how long ago it was made and, per chosen outcome, what moved. Each outcome reads improved, degraded, no change, no evidence, or orphaned. Render it once, then one sentence — never restate in prose what the card shows.",
    {
      title: { type: "string" },
      decided_at: { type: "string", description: "When the decision was recorded." },
      days_elapsed: {
        type: "integer",
        minimum: 0,
        description: "Days between the decision and the supplied today.",
      },
      stale: {
        type: "boolean",
        description: "True when the decision is older than a quarter. Never a reason to hide it.",
      },
      summary: {
        type: "string",
        description: "One line naming how many outcomes moved and how many could not be measured.",
      },
      outcomes: {
        type: "array",
        minItems: 0,
        maxItems: 40,
        items: {
          type: "object",
          properties: {
            outcome_id: { type: "string" },
            statement: {
              type: "string",
              description: "The outcome statement. Omit it when the outcome was deleted.",
            },
            state: {
              enum: ["improved", "degraded", "no change", "no_evidence", "orphaned"],
              description:
                "A missing measurement is \"no_evidence\"; a deleted outcome is \"orphaned\". Neither is a change.",
            },
            satisfaction_change: {
              type: "number",
              description:
                "The signed satisfaction delta. Omit it when either snapshot lacked the metric; the card shows \"not measured\".",
            },
            importance_change: { type: "number" },
            opportunity_change: { type: "number" },
          },
          required: ["outcome_id", "state"],
        },
      },
    },
    ["outcomes"],
  ),
  entry(
    "bet",
    "leaf",
    "A recorded expectation: the hypothesis, the outcome it targets, the baseline captured at creation, the target, and the date to look. Render it once, then one sentence — never restate in prose what the card shows.",
    {
      title: { type: "string" },
      hypothesis: { type: "string", description: "What we expect to happen, in plain words." },
      outcome_id: { type: "string", description: "The outcome the bet targets." },
      baseline: {
        type: "number",
        description:
          "The measurement captured when the bet was created. It is stored, never recomputed from the live score.",
      },
      target: { type: "number", description: "The number we intend to reach." },
      measure_by: { type: "string", description: "The date we will look at the number." },
      status: {
        enum: ["planned", "running", "measured", "abandoned"],
        description: "Where the bet is in its life. measured and abandoned are terminal.",
      },
    },
    ["hypothesis", "baseline", "target", "measure_by", "status"],
  ),
  entry(
    "segment-profile",
    "leaf",
    "A segment's servability: how many members are measured, the underserved and overserved counts kept apart, and the top outcome on each side. A ratio of nothing renders as not measured, never zero. Render it once, then one sentence — never restate in prose what the card shows.",
    {
      title: { type: "string", description: "The segment's name." },
      total_members: { type: "number", description: "How many outcomes the segment holds." },
      measured_count: {
        type: "number",
        description: "Members with a measured score. The rest are unscored or missing.",
      },
      unscored_count: {
        type: "number",
        description: "Members whose scores exist but have no measured basis.",
      },
      missing_count: {
        type: "number",
        description: "Members whose outcome no longer exists. Named, never silently dropped.",
      },
      underserved_count: { type: "number" },
      appropriate_count: { type: "number" },
      overserved_count: { type: "number" },
      measured_ratio: {
        type: "number",
        description:
          "The measured share of the segment. Omitted or null when nothing is measured — never zero, because we did not look.",
      },
      top_underserved: {
        type: "array",
        description: "The strongest underserved outcomes, most severe first.",
        items: {
          type: "object",
          properties: {
            outcome_id: { type: "string" },
            statement: { type: "string" },
            score: { type: "number" },
            band: { enum: ["underserved", "appropriate", "overserved", "unscored"] },
          },
        },
      },
      top_overserved: {
        type: "array",
        description: "The strongest overserved outcomes, most severe first.",
        items: {
          type: "object",
          properties: {
            outcome_id: { type: "string" },
            statement: { type: "string" },
            score: { type: "number" },
            band: { enum: ["underserved", "appropriate", "overserved", "unscored"] },
          },
        },
      },
      strategy: {
        type: "string",
        description: "The recorded strategy for this segment, if one has been chosen.",
      },
      gaps: {
        type: "array",
        description: "What is missing or unscored, stated in words rather than hidden.",
      },
    },
    ["total_members", "measured_count", "underserved_count", "overserved_count"],
  ),
];

const CATALOG_TYPES = new Set(CATALOG.map((component) => component.type));

export function isKnownType(type: string): boolean {
  return CATALOG_TYPES.has(type);
}

export function catalogManifest() {
  return toManifest([...CATALOG]);
}

function formatProp(name: string, schema: UiPropSchema, required: boolean): string {
  let type = schema.type ?? "value";
  if (schema.enum) {
    type = schema.enum.map((value) => `"${value}"`).join(" | ");
  } else if (schema.type === "array") {
    type = "array";
  } else if (schema.type === "number" || schema.type === "integer") {
    const bounds =
      schema.minimum !== undefined && schema.maximum !== undefined
        ? ` ${schema.minimum}–${schema.maximum}`
        : "";
    type = `${schema.type}${bounds}`;
  }
  return `${name}${required ? "" : "?"}: ${type}`;
}

/**
 * Compact, human-readable catalog for the model. Descriptions are the contract:
 * they tell the model *when* to reach for a component, not just what it takes.
 */
export function catalogPrompt(): string {
  return CATALOG.map((component) => {
    const required = new Set(component.props.required ?? []);
    const props = Object.entries(component.props.properties ?? {})
      .filter(([name]) => name !== "actions")
      .map(([name, schema]) => formatProp(name, schema, required.has(name)))
      .join(", ");
    const children = component.acceptsChildren ? " Children allowed." : "";
    const actions = "actions" in (component.props.properties ?? {})
      ? " Optional actions."
      : "";
    return `- ${component.type}(${props}) — ${component.description}${children}${actions}`;
  }).join("\n");
}
