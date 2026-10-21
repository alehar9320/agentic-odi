import { apiUrl } from "../bridge/desktopBridge";
import type {
  AddOutcomePayload,
  AddStepPayload,
  CanvasData,
  ChangelogData,
  ChatStreamRequest,
  LlmHealth,
  McpHealth,
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

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(apiUrl(path), {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(body),
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
