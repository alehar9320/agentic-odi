import { apiUrl } from "../bridge/desktopBridge";
import type {
  AddConnectorPayload,
  AddOutcomePayload,
  AddStepPayload,
  CanvasData,
  ChangelogData,
  ChatStreamRequest,
  ConnectorHealth,
  ConnectorListItem,
  ConnectorOperationResponse,
  ConnectorPreset,
  Conversation,
  CreateJobPayload,
  LatestConversation,
  LlmHealth,
  McpHealth,
  Observation,
  ObservationKind,
  ObservationStatus,
  StudioConfig,
} from "../types";
import { createSseParser, type RawSseEvent } from "./sse";

async function errorDetail(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: string };
    return body.detail ?? `Request failed (${response.status})`;
  } catch {
    return `Request failed (${response.status})`;
  }
}

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(apiUrl(path), { headers: { Accept: "application/json" } });
  if (!response.ok) {
    throw new Error(await errorDetail(response));
  }
  return (await response.json()) as T;
}

async function sendJson<T>(method: "POST" | "PATCH", path: string, body: unknown): Promise<T> {
  const response = await fetch(apiUrl(path), {
    method,
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(await errorDetail(response));
  }
  return (await response.json()) as T;
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  return sendJson<T>("POST", path, body);
}

async function deleteJson<T>(path: string): Promise<T> {
  const response = await fetch(apiUrl(path), {
    method: "DELETE",
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error(await errorDetail(response));
  }
  return (await response.json()) as T;
}

export async function fetchConfig(): Promise<StudioConfig> {
  const body = await getJson<{ defaults: StudioConfig }>("/api/config");
  return body.defaults;
}

export function fetchChangelog(): Promise<ChangelogData> {
  return getJson<ChangelogData>("/api/changelog");
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

export function addStep(payload: AddStepPayload): Promise<{ ok: boolean; result: string }> {
  return postJson<{ ok: boolean; result: string }>("/api/steps", payload);
}

export function addOutcome(
  payload: AddOutcomePayload,
): Promise<{ ok: boolean; result: string }> {
  return postJson<{ ok: boolean; result: string }>("/api/outcomes", payload);
}

export function createJob(
  payload: CreateJobPayload,
): Promise<{ ok: boolean; result: { id?: string } | string }> {
  return postJson<{ ok: boolean; result: { id?: string } | string }>("/api/jobs", payload);
}

export function updateJob(
  jobId: string,
  payload: { name?: string; description?: string; mcp_url: string },
): Promise<{ ok: boolean }> {
  return sendJson<{ ok: boolean }>("PATCH", `/api/jobs/${encodeURIComponent(jobId)}`, payload);
}

export function deleteJob(jobId: string, mcpUrl: string): Promise<{ ok: boolean }> {
  return deleteJson<{ ok: boolean }>(
    `/api/jobs/${encodeURIComponent(jobId)}?mcp_url=${encodeURIComponent(mcpUrl)}`,
  );
}

export function updateStep(
  stepId: string,
  payload: { name?: string; order?: number; mcp_url: string },
): Promise<{ ok: boolean }> {
  return sendJson<{ ok: boolean }>("PATCH", `/api/steps/${encodeURIComponent(stepId)}`, payload);
}

export function deleteStep(stepId: string, mcpUrl: string): Promise<{ ok: boolean }> {
  return deleteJson<{ ok: boolean }>(
    `/api/steps/${encodeURIComponent(stepId)}?mcp_url=${encodeURIComponent(mcpUrl)}`,
  );
}

export function updateOutcome(
  outcomeId: string,
  payload: { statement?: string; importance?: number; satisfaction?: number; mcp_url: string },
): Promise<{ ok: boolean }> {
  return sendJson<{ ok: boolean }>(
    "PATCH",
    `/api/outcomes/${encodeURIComponent(outcomeId)}`,
    payload,
  );
}

export function deleteOutcome(outcomeId: string, mcpUrl: string): Promise<{ ok: boolean }> {
  return deleteJson<{ ok: boolean }>(
    `/api/outcomes/${encodeURIComponent(outcomeId)}?mcp_url=${encodeURIComponent(mcpUrl)}`,
  );
}

export function fetchConnectorCatalog(): Promise<ConnectorPreset[]> {
  return getJson<ConnectorPreset[]>("/api/connectors/catalog");
}

export function fetchConnectors(): Promise<ConnectorListItem[]> {
  return getJson<ConnectorListItem[]>("/api/connectors");
}

export function addConnector(payload: AddConnectorPayload): Promise<ConnectorOperationResponse> {
  return postJson<ConnectorOperationResponse>("/api/connectors", payload);
}

export async function deleteConnector(name: string): Promise<ConnectorOperationResponse> {
  const response = await fetch(apiUrl(`/api/connectors/${encodeURIComponent(name)}`), {
    method: "DELETE",
    headers: { Accept: "application/json" },
  });
  if (!response.ok) throw new Error(await errorDetail(response));
  return (await response.json()) as ConnectorOperationResponse;
}

export function checkConnectorHealth(name: string): Promise<ConnectorHealth> {
  return postJson<ConnectorHealth>(`/api/connectors/${encodeURIComponent(name)}/health`, {});
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
    throw new Error(await errorDetail(response));
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
