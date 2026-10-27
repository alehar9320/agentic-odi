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

export interface EvidenceItem {
  id: string;
  source_name: string;
  source_kind: string;
  item_type: string;
  name: string;
  content: string;
  url?: string | null;
  job_id?: string | null;
  step_id?: string | null;
  outcome_id?: string | null;
  raw?: Record<string, any>;
}

export interface CanvasData {
  jobs: Job[];
  steps: Step[];
  outcomes: Outcome[];
  evidence?: EvidenceItem[];
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

export interface ChatMessage {
  role: "user" | "assistant" | "notice";
  content: string;
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
