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

export interface CanvasData {
  jobs: Job[];
  steps: Step[];
  outcomes: Outcome[];
  source: "mcp" | "seed" | "local";
}

export interface StudioConfig {
  base_url: string;
  api_key: string;
  model_name: string;
  mcp_url: string;
}

export interface LlmHealth {
  healthy: boolean;
  message: string;
}

export interface McpHealth {
  reachable: boolean;
}

export type ChatPart =
  | { kind: "text"; text: string }
  | { kind: "ui"; id: string; node: UiNode };

export interface ChatMessage {
  role: "user" | "assistant" | "notice";
  content: string;
  /**
   * Assistant turns only: prose and surfaces in the order the agent produced
   * them, so a card sits between the paragraphs that frame it. `content` stays
   * the combined prose because that is what gets replayed as history.
   */
  parts?: ChatPart[];
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

/** Secondary surfaces reachable from the drawer. Chat stays the primary stage. */
export type WorkspacePanelId =
  | "landscape"
  | "jobmap"
  | "impact"
  | "evidence"
  | "capture"
  | "settings";

export interface ChatStreamRequest {
  base_url: string;
  api_key: string;
  model: string;
  mcp_url: string;
  messages: ChatMessage[];
  brief?: StudioBrief | null;
  /** What this client can render. Omitted by clients that only read prose. */
  ui_catalog?: UiCatalogManifest;
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
