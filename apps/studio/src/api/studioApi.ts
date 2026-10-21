import { apiUrl } from "../bridge/desktopBridge";
import type {
  AddOutcomePayload,
  AddStepPayload,
  CanvasData,
  ChatStreamRequest,
  LlmHealth,
  McpHealth,
  Observation,
  ObservationKind,
  ObservationStatus,
  Outcome,
  Step,
  StudioConfig,
  StudioError,
} from "../types";
import { createSseParser, type RawSseEvent } from "./sse";

/** A failure the sidecar reported, kept whole so the UI can show it. */
export class StudioApiError extends Error {
  readonly error: StudioError;

  constructor(error: StudioError) {
    super(error.message);
    this.name = "StudioApiError";
    this.error = error;
  }
}

/** Turn anything thrown into the shared error shape. */
export function asStudioError(error: unknown): StudioError {
  if (error instanceof StudioApiError) {
    return error.error;
  }
  if (error instanceof Error) {
    return {
      code: "internal",
      message: error.message || "Something went wrong.",
      retryable: false,
    };
  }
  return {
    code: "internal",
    message: "Something went wrong.",
    retryable: false,
  };
}

async function studioError(response: Response): Promise<StudioApiError> {
  let body: { error?: StudioError; detail?: string };
  try {
    body = (await response.json()) as { error?: StudioError; detail?: string };
  } catch {
    body = {};
  }

  if (body.error && typeof body.error === "object" && typeof body.error.code === "string") {
    return new StudioApiError({
      ...body.error,
      retryable: body.error.retryable ?? false,
      message: body.error.message || `Request failed (${response.status})`,
    });
  }
  if (typeof body.detail === "string" && body.detail) {
    return new StudioApiError({
      code: "internal",
      message: body.detail,
      retryable: false,
    });
  }
  return new StudioApiError({
    code: "internal",
    message: `Request failed (${response.status})`,
    retryable: false,
  });
}

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(apiUrl(path), { headers: { Accept: "application/json" } });
  if (!response.ok) {
    throw await studioError(response);
  }
  return (await response.json()) as T;
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(apiUrl(path), {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw await studioError(response);
  }
  return (await response.json()) as T;
}

export async function fetchConfig(): Promise<StudioConfig> {
  const body = await getJson<{ defaults: StudioConfig }>("/api/config");
  return body.defaults;
}

export function fetchCanvas(mcpUrl: string): Promise<CanvasData> {
  return getJson<CanvasData>(`/api/canvas?mcp_url=${encodeURIComponent(mcpUrl)}`);
}

export function healthMcp(mcpUrl: string): Promise<McpHealth> {
  return postJson<McpHealth>("/api/health/mcp", { mcp_url: mcpUrl });
}

export function healthLlm(config: {
  base_url: string;
  api_key: string;
  model: string;
}): Promise<LlmHealth> {
  return postJson<LlmHealth>("/api/health/llm", config);
}

export function addStep(payload: AddStepPayload): Promise<Step> {
  return postJson<Step>("/api/steps", payload);
}

export function addOutcome(payload: AddOutcomePayload): Promise<Outcome> {
  return postJson<Outcome>("/api/outcomes", payload);
}

export type ChatEventHandler = (event: RawSseEvent) => void;

export async function streamChat(
  request: ChatStreamRequest,
  onEvent: ChatEventHandler,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(apiUrl("/api/chat"), {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify(request),
    signal,
  });

  if (!response.ok || !response.body) {
    throw await studioError(response);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  const parser = createSseParser();

  for (;;) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }
    for (const event of parser.push(decoder.decode(value, { stream: true }))) {
      onEvent(event);
    }
  }
}


export async function fetchMemory(): Promise<Observation[]> {
  const body = await getJson<{ observations: Observation[] }>("/api/memory/observations");
  return body.observations;
}

export interface AddObservationPayload {
  kind: ObservationKind;
  text: string;
  data?: Record<string, unknown>;
  confidence?: number;
  confirmed?: boolean;
}

export async function addObservation(payload: AddObservationPayload): Promise<Observation> {
  const body = await postJson<{ observation: Observation }>("/api/memory/observations", payload);
  return body.observation;
}

export interface UpdateObservationPayload {
  text?: string;
  status?: ObservationStatus;
  data?: Record<string, unknown>;
  confidence?: number;
}

export async function updateObservation(
  observationId: string,
  payload: UpdateObservationPayload,
): Promise<Observation> {
  const body = await sendJson<{ observation: Observation }>(
    "PATCH",
    `/api/memory/observations/${encodeURIComponent(observationId)}`,
    payload,
  );
  return body.observation;
}

export function deleteObservation(observationId: string): Promise<{ ok: boolean }> {
  return deleteJson<{ ok: boolean }>(
    `/api/memory/observations/${encodeURIComponent(observationId)}`,
  );
}

export function clearMemory(): Promise<{ ok: boolean }> {
  return deleteJson<{ ok: boolean }>("/api/memory");
}

export function fetchLatestConversation(): Promise<LatestConversation> {
  return getJson<LatestConversation>("/api/conversations/latest");
}

export async function createConversation(): Promise<Conversation> {
  const body = await postJson<{ conversation: Conversation }>("/api/conversations", {});
  return body.conversation;
}
