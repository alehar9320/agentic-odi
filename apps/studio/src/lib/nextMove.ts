import { JOB_STAGES } from "../domain/jobStages";
import type {
  CanvasProvenance,
  ChatMessage,
  Evidence,
  Job,
  Outcome,
  Signal,
  Step,
  StudioBrief,
  Thesis,
  WorkspacePanelId,
} from "../types";

/**
 * The one move the studio recommends at the end of a turn.
 *
 * Pure and React-free: every word is computed from state, never authored by a
 * model. A card that cannot explain why now, and what would make it
 * unnecessary, is a banner, not advice.
 */

export type NextMoveKind = "context" | "evidence" | "score" | "map" | "signal" | "decide";

export type NextMoveAction =
  | { label: string; kind: "prompt"; prompt: string }
  | { label: string; kind: "panel"; panel: WorkspacePanelId }
  | { label: string; kind: "setup" };

export interface NextMove {
  /** Stable hash of kind + subject + last turn, so one dismissal hides one move. */
  id: string;
  kind: NextMoveKind;
  move: string;
  rationale: string;
  expectedEvidence: string;
  action: NextMoveAction;
}

export interface LastTurn {
  messageId: string;
  toolNames: string[];
  touchedOutcomeIds: string[];
}

export interface NextMoveCanvas {
  jobs: Job[];
  steps: Step[];
  outcomes: Outcome[];
  evidence: Evidence[];
  provenance?: CanvasProvenance;
}

export interface NextMoveInput {
  brief: StudioBrief | null;
  lastTurn: LastTurn | null;
  canvas: NextMoveCanvas | null;
  signals: Signal[];
  theses: Thesis[];
  dismissedId: string | null;
  /** When false, a chat-only prompt is replaced by the panel that works offline. */
  modelAvailable: boolean;
}

const SCORING_TOOLS = new Set(["add_outcome", "update_outcome"]);
const KIND_LABELS: Record<NextMoveKind, string> = {
  context: "Context",
  evidence: "Evidence",
  score: "Score",
  map: "Job map",
  signal: "Signal",
  decide: "Decision",
};

export function nextMoveKindLabel(kind: NextMoveKind): string {
  return KIND_LABELS[kind];
}

function stableId(kind: NextMoveKind, subject: string, turn: string): string {
  let hash = 5381;
  for (const character of `${kind}:${subject}:${turn}`) {
    hash = ((hash << 5) + hash + character.charCodeAt(0)) >>> 0;
  }
  return `${kind}-${hash.toString(36)}`;
}

function shortStatement(statement: string | undefined): string {
  const text = (statement ?? "this outcome").trim();
  return text.length > 60 ? `${text.slice(0, 57)}…` : text;
}

/**
 * The last assistant turn and the tools it called.
 *
 * Outcome ids are not carried in a chat part, so the ladder treats a scored
 * outcome as touched when the turn called a scoring tool as well as when an id
 * is supplied explicitly.
 */
export function lastAssistantTurn(messages: ChatMessage[]): LastTurn | null {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index];
    if (message.role !== "assistant") {
      continue;
    }
    const toolNames = (message.parts ?? [])
      .filter((part) => part.kind === "tool")
      .map((part) => part.name);
    return { messageId: message.id, toolNames, touchedOutcomeIds: [] };
  }
  return null;
}

function samplePrefix(canvas: NextMoveCanvas | null): string {
  return canvas?.provenance && canvas.provenance.kind !== "live" ? "Sample data: " : "";
}

export function recommendNextMove(input: NextMoveInput): NextMove | null {
  if (!input.lastTurn) {
    return null;
  }

  const turn = input.lastTurn.messageId;
  const prefix = samplePrefix(input.canvas);
  const brief = input.brief;
  const canvas = input.canvas;
  const outcomes = canvas?.outcomes ?? [];
  const evidence = canvas?.evidence ?? [];

  // 1. No brief: every answer is generic until the studio knows the product.
  if (!brief) {
    return {
      id: stableId("context", "brief", turn),
      kind: "context",
      move: "Tell the studio what you are building.",
      rationale: `${prefix}Every answer is generic until the studio knows the product.`,
      expectedEvidence: "A product name and the job it serves.",
      action: { label: "Add context", kind: "setup" },
    };
  }

  // 2. A score with no linked evidence is the most misleading state. Join on
  // evidence.outcome_id; never read a phantom outcome.evidence field.
  const scored = outcomes.filter(
    (outcome) => outcome.importance != null && outcome.satisfaction != null,
  );
  const touched = new Set(input.lastTurn.touchedOutcomeIds);
  let candidates = scored.filter((outcome) => touched.has(outcome.id ?? ""));
  if (
    candidates.length === 0 &&
    input.lastTurn.toolNames.some((name) => SCORING_TOOLS.has(name))
  ) {
    candidates = scored;
  }
  const unlinked = candidates.find(
    (outcome) => !evidence.some((record) => record.outcome_id === outcome.id),
  );
  if (unlinked) {
    const score = unlinked.opportunity_score ?? 0;
    return {
      id: stableId("evidence", unlinked.id ?? "outcome", turn),
      kind: "evidence",
      move: `Ask two ${brief.target_user} how they do this today.`,
      rationale: `${prefix}You scored this outcome at ${score.toFixed(1)} and no evidence is linked to it.`,
      expectedEvidence: "One quote describing the workaround.",
      action: input.modelAvailable
        ? {
            label: "Draft the ask",
            kind: "prompt",
            prompt:
              "I want to capture what a customer actually does today. Ask me what they said, then help me turn it into an outcome.",
          }
        : { label: "Open capture", kind: "panel", panel: "capture" },
    };
  }

  // 3. An urgent signal outranks map hygiene: it is already waiting.
  const urgent = input.signals.find(
    (signal) =>
      signal.severity === "urgent" &&
      !signal.read_at &&
      !signal.dismissed_at &&
      !signal.suppressed,
  );
  if (urgent) {
    return {
      id: stableId("signal", urgent.id, turn),
      kind: "signal",
      move: `Decide what to do about ${urgent.title}.`,
      rationale: `${prefix}An urgent signal is waiting in Catch Up.`,
      expectedEvidence: "Act or dismiss it in Catch Up, with the decision recorded.",
      action: { label: "Open Catch Up", kind: "panel", panel: "catchup" },
    };
  }

  // 4. An incomplete job map: name the first missing stage, not a count.
  const jobs = canvas?.jobs ?? [];
  const activeJob = jobs.find((job) => job.id === brief.job_id) ?? jobs[0];
  if (activeJob) {
    const covered = new Set(
      (canvas?.steps ?? [])
        .filter((step) => step.job_id === activeJob.id)
        .map((step) => step.stage)
        .filter((stage): stage is string => Boolean(stage)),
    );
    const missing = JOB_STAGES.find((stage) => !covered.has(stage.id));
    if (missing) {
      return {
        id: stableId("map", `${activeJob.id}:${missing.id}`, turn),
        kind: "map",
        move: `Map the ${missing.name.replace(/^\d+\.\s*/, "").toLowerCase()} stage of ${activeJob.name ?? "this job"}.`,
        rationale: `${prefix}The job map covers ${covered.size} of ${JOB_STAGES.length} stages.`,
        expectedEvidence: "One step with a stage.",
        action: { label: "Open the job map", kind: "panel", panel: "jobmap" },
      };
    }
  }

  // 5. An underserved outcome with no recorded decision.
  const undecided = outcomes
    .filter(
      (outcome) =>
        (outcome.opportunity_score ?? 0) > 10 &&
        !input.theses.some((thesis) => thesis.outcome_id === outcome.id),
    )
    .sort((a, b) => (b.opportunity_score ?? 0) - (a.opportunity_score ?? 0))[0];
  if (undecided) {
    const score = undecided.opportunity_score ?? 0;
    const statement = shortStatement(undecided.statement);
    return {
      id: stableId("decide", undecided.id ?? statement, turn),
      kind: "decide",
      move: `Pressure-test “${statement}”.`,
      rationale: `${prefix}This outcome scores ${score.toFixed(1)} and no thesis records a decision.`,
      expectedEvidence: "A decision to chase or park it.",
      action: input.modelAvailable
        ? {
            label: "Pressure-test",
            kind: "prompt",
            prompt: `Pressure-test this outcome with me: ${undecided.statement ?? statement}`,
          }
        : { label: "Open the landscape", kind: "panel", panel: "landscape" },
    };
  }

  // 6. Nothing to reason from yet: capture one outcome by hand.
  return {
    id: stableId("score", "capture", turn),
    kind: "score",
    move: "Capture one outcome by hand.",
    rationale: `${prefix}There is no scored outcome to reason from yet.`,
    expectedEvidence: "One outcome with importance and satisfaction.",
    action: { label: "Open capture", kind: "panel", panel: "capture" },
  };
}
