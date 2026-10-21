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
  /** Why the board is not what the server actually holds, when the sidecar knows. */
  warnings?: string[];
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
  role: "user" | "assistant";
  content: string;
}

export interface ChatStreamRequest {
  base_url: string;
  api_key: string;
  model: string;
  mcp_url: string;
  messages: ChatMessage[];
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
