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
    "segment-card",
    "leaf",
    "One outcome-based segment (Stage 5): the people, the job they are doing, and the verdict their scored outcomes support. Never a demographic grouping.",
    {
      id: { type: "string" },
      name: {
        type: "string",
        description: 'Composed from the evidence: "<the people>, <the step they are stuck on>".',
      },
      people: {
        type: "string",
        description: "The group in their own words when those words are on record.",
      },
      peopleInferred: {
        type: "boolean",
        description: "True when `people` was derived from the outcomes rather than supplied.",
      },
      jobStatement: { type: "string", description: "The functional job this segment is doing." },
      verdict: {
        enum: ["underserved", "overserved", "appropriately_served", "unknown"],
        description:
          '"unknown" when any outcome is unscored — an unclassifiable segment is reported, not guessed.',
      },
      confidence: {
        type: "number",
        minimum: 0,
        maximum: 1,
        description: "How much evidence stands behind the verdict. Never shown apart from it.",
      },
      outcomeIds: {
        type: "array",
        minItems: 2,
        maxItems: 40,
        items: { type: "string" },
        description: "The outcomes this segment rests on. Two is the floor: one is a hypothesis.",
      },
      rationale: { type: "string", description: "Why this verdict, naming the outcomes behind it." },
      unclustered: {
        type: "array",
        maxItems: 40,
        items: { type: "string" },
        description: "Outcome ids that joined no segment. Shown as their own group, never dropped.",
      },
    },
    ["id", "name", "people", "jobStatement", "verdict", "confidence", "rationale"],
  ),
  entry(
    "strategy-card",
    "leaf",
    "The one innovation path the segments support (Stage 6), with every path it beat and why.",
    {
      id: { type: "string" },
      kind: {
        enum: ["differentiated", "disruptive", "new_market"],
        description: "Improve for an underserved segment, undercut an overserved one, or serve a job nobody serves.",
      },
      segmentId: { type: "string", description: "The segment this bet is aimed at, when there is one." },
      thesis: {
        type: "string",
        description: "Why this path, from the evidence — it names the outcomes, not a hunch.",
      },
      bets: {
        type: "array",
        maxItems: 6,
        items: { type: "string" },
        description: "The concrete moves proposed.",
      },
      rejected: {
        type: "array",
        minItems: 2,
        maxItems: 2,
        description:
          "One entry per path not chosen, with the reason. A strategy without these is a conclusion, not a recommendation.",
        items: {
          type: "object",
          properties: {
            kind: { enum: ["differentiated", "disruptive", "new_market"] },
            why: { type: "string" },
          },
          required: ["kind", "why"],
        },
      },
    },
    ["kind", "thesis", "rejected"],
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
