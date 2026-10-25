/**
 * What a run actually did.
 *
 * The sidecar streams one `tool` event per state change: `start` when a call
 * begins, then `ok` or `error` when it resolves. A transcript that appends every
 * event shows the same tool twice and never says whether it finished, which is
 * the difference between "the studio is working" and "the studio is stuck".
 *
 * So events are folded into ordered steps here — one per call, with the time it
 * took and how it ended. Everything in this module is pure and takes `now`, so
 * the timeline can be reasoned about (and tested) without a clock.
 */

export type RunStepStatus = "running" | "ok" | "error" | "stopped";

export interface RunStep {
  /** Stable across updates, so React keeps the row it was already showing. */
  id: string;
  /** The raw tool name, kept so the UI can always fall back to it. */
  name: string;
  status: RunStepStatus;
  /** The tool's own words on failure, or a short result note. */
  preview?: string;
  startedAt: number;
  endedAt?: number;
}

/** The `tool` event the sidecar emits. */
export interface ToolEvent {
  name: string;
  status: string;
  preview?: string;
}

/**
 * Tool names as the studio says them out loud. Unknown tools still get a
 * readable label from their own name — a model can call anything the MCP
 * server offers, so this table is a nicety, never a requirement.
 */
const TOOL_LABELS: Record<string, string> = {
  render_ui: "Drawing a card",
  remember: "Saving what it learned",
  add_connector: "Connecting a tool",
  add_job: "Adding a job",
  get_jobs: "Reading your jobs",
  get_job: "Opening a job",
  update_job: "Updating a job",
  delete_job: "Removing a job",
  add_step: "Adding a step",
  get_step: "Reading a step",
  get_job_map: "Reading the job map",
  update_step: "Updating a step",
  delete_step: "Removing a step",
  add_outcome: "Adding an outcome",
  get_outcomes: "Scoring outcomes",
  get_outcome: "Reading an outcome",
  update_outcome: "Updating an outcome",
  delete_outcome: "Removing an outcome",
  add_customer_outcome: "Capturing what you heard",
  get_customer_outcome: "Reading what you heard",
  list_customer_outcomes: "Reading what you heard",
  update_customer_outcome: "Updating what you heard",
  delete_customer_outcome: "Removing what you heard",
  compute_opportunity: "Scoring the opportunity",
  evaluate_outcome: "Evaluating an outcome",
  add_evidence: "Saving evidence",
  get_evidence: "Reading evidence",
  list_evidence: "Reading evidence",
  delete_evidence: "Removing evidence",
  promote_evidence: "Promoting evidence",
  get_odi_framework_guidelines: "Checking the ODI framework",
  get_odi_schema: "Checking the ODI schema",
  get_capabilities: "Checking what it can do",
};

const PHASE_LABELS: Record<string, string> = {
  health_check: "Waking the model",
  mcp_tools: "Opening your studio tools",
  model: "Thinking",
  offline: "Working without a model",
};

/** A tool name as a phrase a person would say, e.g. "Reading your jobs". */
export function stepLabel(name: string): string {
  const known = TOOL_LABELS[name];
  if (known) {
    return known;
  }
  const humanized = name.replace(/[_-]+/g, " ").trim();
  return humanized || "Using a tool";
}

function lastOpenStep(steps: RunStep[], name: string): number {
  for (let index = steps.length - 1; index >= 0; index -= 1) {
    const step = steps[index];
    if (step.status === "running" && step.name === name) {
      return index;
    }
  }
  return -1;
}

/**
 * Fold one `tool` event into the timeline.
 *
 * A `start` opens a step; `ok`/`error` resolves the newest open step with that
 * name. A result with no matching start (a replayed stream, a client that
 * joined late) becomes a finished step rather than being dropped.
 */
export function applyToolEvent(steps: RunStep[], event: ToolEvent, now: number): RunStep[] {
  const name = event.name.trim() || "tool";

  if (event.status === "start") {
    return [
      ...steps,
      {
        id: `${name}-${steps.length}`,
        name,
        status: "running",
        startedAt: now,
      },
    ];
  }

  const status: RunStepStatus = event.status === "error" ? "error" : "ok";
  const open = lastOpenStep(steps, name);
  if (open === -1) {
    return [
      ...steps,
      {
        id: `${name}-${steps.length}`,
        name,
        status,
        preview: event.preview,
        startedAt: now,
        endedAt: now,
      },
    ];
  }

  return steps.map((step, index) =>
    index === open
      ? { ...step, status, preview: event.preview ?? step.preview, endedAt: now }
      : step,
  );
}

/** Durations are read at a glance, so they stay to one short form. */
export function formatDuration(ms: number): string {
  if (!Number.isFinite(ms) || ms < 0) {
    return "0s";
  }
  if (ms < 1000) {
    return `${(ms / 1000).toFixed(1)}s`;
  }
  if (ms < 60_000) {
    const seconds = ms / 1000;
    return `${seconds < 10 ? seconds.toFixed(1) : Math.round(seconds)}s`;
  }
  const minutes = Math.floor(ms / 60_000);
  const seconds = Math.round((ms % 60_000) / 1000);
  return `${minutes}m ${seconds}s`;
}

/** The step still in flight, if the run has one. */
export function runningStep(steps: RunStep[]): RunStep | null {
  for (let index = steps.length - 1; index >= 0; index -= 1) {
    if (steps[index].status === "running") {
      return steps[index];
    }
  }
  return null;
}

/**
 * What the studio is doing right now: the tool it is waiting on, or the phase
 * it is in. Deliberately about work, never about the model's reasoning.
 */
export function activityLabel(phase: string | null, steps: RunStep[]): string {
  const running = runningStep(steps);
  if (running) {
    return stepLabel(running.name);
  }
  return (phase ? PHASE_LABELS[phase] : undefined) ?? "Thinking";
}

/**
 * The one line a finished run leaves behind. Counts and time only: the point is
 * that work happened, not a replay of every call.
 */
export function runSummary(steps: RunStep[], now: number): string {
  if (!steps.length) {
    return "";
  }
  const started = Math.min(...steps.map((step) => step.startedAt));
  const ended = Math.max(...steps.map((step) => step.endedAt ?? now));
  const failures = steps.filter((step) => step.status === "error").length;
  const parts = [`${steps.length} tool${steps.length === 1 ? "" : "s"}`];
  if (failures) {
    parts.push(`${failures} failed`);
  }
  parts.push(formatDuration(ended - started));
  return parts.join(" · ");
}
