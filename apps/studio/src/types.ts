import type { UiCatalogManifest, UiNode } from "./ui/protocol";

export interface Job {
  id: string;
  name?: string;
  description?: string;
}

export interface Step {
  id?: string;
  job_id?: string;
  name?: string;
  order?: number;
}

export interface Outcome {
  id?: string;
  job_id?: string;
  statement?: string;
  importance?: number | null;
  satisfaction?: number | null;
  opportunity_score?: number | null;
  evidence?: string;
  telemetry?: string;
}

export interface Evidence {
  id: string;
  source_name?: string;
  source_kind?: string;
  item_type?: string;
  name?: string;
  content?: string;
  job_id?: string | null;
  step_id?: string | null;
  outcome_id?: string | null;
}

export interface Thesis {
  id: string;
  outcome_id: string;
  job_id?: string;
  statement: string;
  importance: number | null;
  satisfaction: number | null;
  opportunity_score: number | null;
  rationale: string;
  created_at: string;
}

export type CanvasProvenanceKind = "live" | "seed" | "empty";

/**
 * Where the canvas came from. The sidecar labels every response so the studio
 * can say "sample data" instead of presenting the prototype as the user's work.
 * Optional because a canvas cached by an older build has no provenance.
 */
export interface CanvasProvenance {
  kind: CanvasProvenanceKind;
  reason: string;
  generated_at: string;
  record_counts: {
    jobs: number;
    steps: number;
    outcomes: number;
    evidence: number;
  };
}

export interface CanvasData {
  jobs: Job[];
  steps: Step[];
  outcomes: Outcome[];
  /** Captured research records, in capture order until the user reorders them. */
  evidence?: Evidence[];
  source: "mcp" | "seed" | "local";
  /** Why the board is not what the server actually holds, when the sidecar knows. */
  warnings?: string[];
  provenance?: CanvasProvenance;
}

/**
 * What the canvas currently is. A union, not four booleans: "no work yet" and
 * "the fetch failed" look identical if you only track emptiness, and a failed
 * canvas must never render as an empty one.
 */
export type CanvasState =
  | { kind: "loading"; data: CanvasData | null }
  | { kind: "ready"; data: CanvasData }
  | { kind: "empty"; data: CanvasData }
  | { kind: "error"; error: StudioError; data: CanvasData | null };

/**
 * The one failure shape the sidecar reports. Every HTTP error arrives as
 * `{"error": StudioError}`, so the UI can show what went wrong, what to do
 * about it, and whether a retry is worth trying.
 */
export interface StudioError {
  code: string;
  message: string;
  detail?: string | null;
  suggestion?: string | null;
  retryable: boolean;
  request_id?: string | null;
}

export type StudioTheme = "light" | "dark";

export interface StudioConfig {
  base_url: string;
  api_key: string;
  model_name: string;
  mcp_url: string;
  theme?: StudioTheme;
}

export interface LlmHealth {
  healthy: boolean;
  message: string;
}

/** What the configured backend reports it can serve, and why it reported none. */
export interface ModelList {
  models: string[];
  error: string | null;
}

export interface McpHealth {
  reachable: boolean;
}

/**
 * Everything one turn can contain, in the order the agent produced it.
 *
 * Text and surfaces are the Studio's own vocabulary. Reasoning, tool calls,
 * sources, approvals, and attachments are conversation primitives the runtime
 * renders — the bridge in `assistant/convert.ts` maps each one to its
 * assistant-ui message part.
 */
export type ToolStatus = "running" | "ok" | "error" | "declined";

/** A write the agent is asking permission for. */
export interface ToolApproval {
  id: string;
  prompt: string;
}

export interface ChatAttachment {
  id: string;
  name: string;
  contentType: string;
  size: number;
  /** Extracted text, sent to the model when the file is text-like. */
  text?: string;
  /** A data URL, sent as a vision part when the file is an image. */
  dataUrl?: string;
}

export type ChatPart =
  | { kind: "text"; text: string }
  | { kind: "reasoning"; text: string }
  | { kind: "ui"; id: string; node: UiNode }
  | {
      kind: "tool";
      id: string;
      name: string;
      status: ToolStatus;
      preview?: string;
      /** Present while the runtime is waiting for the user's answer. */
      approval?: ToolApproval;
    }
  | {
      kind: "source";
      id: string;
      title: string;
      filename?: string;
      mediaType: string;
    };

export interface ChatMessage {
  /** Stable id. Branching and persisted turns are keyed by it. */
  id: string;
  /** The message this one answers; `null` at the root of a branch. */
  parentId: string | null;
  role: "user" | "assistant" | "notice";
  content: string;
  /**
   * Assistant turns only: prose and surfaces in the order the agent produced
   * them, so a card sits between the paragraphs that frame it. `content` stays
   * the combined prose because that is what gets replayed as history.
   */
  parts?: ChatPart[];
  /** Files the user attached to this turn. */
  attachments?: ChatAttachment[];
  /**
   * Assistant turns only: the failure that ended this turn, so the transcript
   * can show it in place instead of losing the question.
   */
  error?: StudioError;
  /** The question this turn answered, kept so a failed turn can be retried. */
  retryText?: string;
}

/**
 * The user's context, captured on first run. Kept in local storage and sent to
 * the sidecar so every reply starts from the user's actual product and job.
 */
export interface StudioBrief {
  product_name: string;
  product_url?: string;
  target_user: string;
  job_statement: string;
  core_problem: string;
  job_id?: string;
}

/**
 * Lenses reachable from the rail and the bar. Chat is always the primary
 * stage; a lens makes room for itself and never replaces the thread.
 */
export type WorkspacePanelId =
  | "landscape"
  | "jobmap"
  | "evidence"
  | "capture"
  | "memory"
  | "catchup"
  | "settings";

/**
 * One recorded fact from the shared store. Kinds are exactly the ones a real
 * mutation can emit; nothing here is invented by the client.
 */
export type SignalKind =
  | "job_added"
  | "outcome_scored"
  | "opportunity_crossed"
  | "evidence_ingested"
  | "evidence_promoted"
  | "job_map_completed";

export type SignalSeverity = "info" | "notice" | "urgent";

export type SignalSubjectKind =
  | "job"
  | "step"
  | "outcome"
  | "evidence"
  | "connector"
  | "agent_work";

export interface Signal {
  id: string;
  kind: SignalKind;
  title: string;
  detail?: string | null;
  subject_kind?: SignalSubjectKind | null;
  subject_id?: string | null;
  severity: SignalSeverity;
  created_at: string;
  read_at?: string | null;
  dismissed_at?: string | null;
  /** Past the daily attention budget: recorded, but never surfaced or counted. */
  suppressed: boolean;
  fingerprint: string;
  /** Only the developer simulator (#78) sets this. Simulated entries never count. */
  simulated?: boolean;
}

export interface ChatStreamRequest {
  base_url: string;
  api_key: string;
  model: string;
  mcp_url: string;
  messages: ChatMessage[];
  brief?: StudioBrief | null;
  /** What this client can render. Omitted by clients that only read prose. */
  ui_catalog?: UiCatalogManifest;
  /** Continue an existing thread instead of starting a new one. */
  conversation_id?: string | null;
  /** Files attached to the last user turn. */
  attachments?: ChatAttachment[];
  /** Ask before the agent writes to stored data. */
  approvals?: boolean;
  /** The id this client is streaming the reply under. */
  assistant_id?: string | null;
}

/** One turn in a persisted conversation, as the branch tree exposes it. */
export interface TurnNode {
  id: string;
  parent_id: string | null;
  role: string;
  content: string;
  created_at: string;
}

export interface ConversationTree {
  conversation: Conversation;
  messages: TurnNode[];
  head_id: string | null;
}

export type ObservationKind =
  | "career"
  | "opportunity"
  | "business"
  | "stakeholder"
  | "constraint"
  | "evidence"
  | "preference";

export type ObservationStatus = "suggested" | "confirmed" | "dismissed";

/** One thing the agent believes about the PM, shown for correction. */
export interface Observation {
  id: string;
  kind: ObservationKind;
  text: string;
  data: Record<string, unknown>;
  status: ObservationStatus;
  confidence: number;
  source_turn: number | null;
  created_at: string;
  updated_at: string;
}

export interface Conversation {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  /** The visible branch head turn, when the conversation has branches. */
  head_id?: string | null;
}

export interface ConversationTurn {
  id: number;
  conversation_id: string;
  role: "user" | "assistant" | "system" | "tool";
  content: string;
  created_at: string;
  /** Stable client message id, when the turn was authored with one. */
  message_id?: string | null;
  /** The id of the turn this one answers, when it is a branch or edit. */
  parent_id?: string | null;
}

export interface LatestConversation {
  conversation: Conversation | null;
  turns: ConversationTurn[];
}

export interface CreateJobPayload {
  name: string;
  description?: string;
  mcp_url: string;
}

export interface AddStepPayload {
  mcp_url: string;
  job_id: string;
  name: string;
  order: number;
}

export interface AddOutcomePayload {
  mcp_url: string;
  job_id: string;
  statement: string;
  importance: number;
  satisfaction: number;
}

export interface ConnectorPreset {
  id: string;
  label: string;
  area: string;
  summary: string;
  url: string;
  auth: "none" | "oauth";
  env_vars: string[];
  headers: Record<string, string>;
  docs: string;
  tools: string[];
  is_recommended: boolean;
}

export interface ConnectorListItem {
  name: string;
  kind: string;
  enabled: boolean;
}

export interface ConnectorHealth {
  ok: boolean;
  message: string;
  details: Record<string, unknown>;
}

export interface ConnectorOperationResponse {
  ok: boolean;
  name: string;
}

export interface AddConnectorPayload {
  name?: string;
  preset?: string;
  url?: string;
}

export interface ChangelogCategory {
  name: string;
  items: string[];
}

export interface ChangelogRelease {
  version: string;
  date: string;
  categories: ChangelogCategory[];
}

export interface ChangelogData {
  releases: ChangelogRelease[];
}
