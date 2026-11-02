import { apiUrl } from "../bridge/desktopBridge";
import { getStudioBff } from "../bff/index";
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
  ConversationSummary,
  ConversationTree,
  CreateJobPayload,
  Job,
  LatestConversation,
  LlmHealth,
  MarketplaceSearch,
  McpHealth,
  ModelList,
  Observation,
  ObservationKind,
  ObservationStatus,
  Outcome,
  Segment,
  Signal,
  Step,
  Strategy,
  StudioConfig,
  StudioError,
  TurnNode,
} from "../types";
import { createSseParser, type RawSseEvent } from "./sse";
import { recordStudioError } from "../diagnostics/bundle";
import { readEdgeTurns, recordEdgeTurn } from "../edge/transcript";

/** A failure the sidecar reported, kept whole so the UI can show it. */
export class StudioApiError extends Error {
  readonly error: StudioError;
  readonly status: number;
  /** True when the body came from the sidecar itself (structured `error` field). False for proxy/detail failures. */
  readonly fromSidecar: boolean;

  constructor(error: StudioError, status = 0, fromSidecar = false) {
    super(error.message);
    this.name = "StudioApiError";
    this.error = error;
    this.status = status;
    this.fromSidecar = fromSidecar;
  }
}

/** Network or sidecar-proxy failures are transport failures; application errors are not. */
export function isTransportFailure(error: unknown): boolean {
  if (error instanceof StudioApiError) {
    return (
      (error.status === 502 || error.status === 503 || error.status === 504) &&
      !error.fromSidecar
    );
  }
  if (error instanceof TypeError) {
    return true;
  }
  if (error && typeof error === "object" && (error as { name?: string }).name === "NetworkError") {
    return true;
  }
  return false;
}

/** Map an HTTP status the sidecar/worker returned (with no body) to a code. */
function codeForStatus(status: number): string {
  if (status === 404) return "not_found";
  if (status === 409) return "conflict";
  if (status === 422 || status === 400) return "validation";
  if (status === 401 || status === 403) return "unauthorized";
  if (status === 429) return "rate_limit";
  if (status === 502 || status === 503) return "mcp_unreachable";
  if (status >= 500) return "internal";
  return "internal";
}

const MESSAGE_FOR_CODE: Partial<Record<string, string>> = {
  mcp_unreachable: "The studio sidecar isn't reachable.",
  not_found: "That resource wasn't found.",
  validation: "The request was invalid.",
  conflict: "That conflicts with the current state.",
  rate_limit: "You're moving too fast.",
  unauthorized: "You're not authorized.",
};

const SUGGESTION_FOR_CODE: Partial<Record<string, string>> = {
  mcp_unreachable:
    "Start the studio sidecar with `python scripts/dev.py` (or `npm --prefix apps/studio run dev:full`), then click Recheck.",
  not_found: "Check the identifier and try again.",
  validation: "Fix the input and try again.",
  conflict: "Reload and try again.",
  rate_limit: "Wait a moment, then retry.",
  unauthorized: "Check your credentials and try again.",
};

const RETRYABLE_FOR_CODE: Partial<Record<string, boolean>> = {
  mcp_unreachable: true,
  rate_limit: true,
};

function retryableForCode(code: string): boolean {
  return RETRYABLE_FOR_CODE[code] ?? false;
}

/** Describe a non-ok response the sidecar/worker returned. */
function describeStatus(status: number): StudioError {
  const code = codeForStatus(status);
  return {
    code,
    message: MESSAGE_FOR_CODE[code] ?? `Request failed (${status})`,
    suggestion: SUGGESTION_FOR_CODE[code],
    retryable: retryableForCode(code),
  };
}

/** Turn anything thrown into the shared error shape. */
export function asStudioError(error: unknown): StudioError {
  if (error instanceof StudioApiError) {
    return error.error;
  }
  // A network-level failure means the sidecar (or the Worker that fronts it)
  // never answered: frame it as a sidecar problem with a path back, not a
  // generic "something went wrong".
  if (error instanceof TypeError || (error instanceof Error && /fetch failed|network error/i.test(error.message))) {
    return {
      code: "mcp_unreachable",
      message: MESSAGE_FOR_CODE.mcp_unreachable ?? "The studio sidecar isn't reachable.",
      suggestion: SUGGESTION_FOR_CODE.mcp_unreachable,
      retryable: RETRYABLE_FOR_CODE.mcp_unreachable ?? true,
    };
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
    return new StudioApiError(
      {
        ...body.error,
        retryable: body.error.retryable ?? false,
        message: body.error.message || `Request failed (${response.status})`,
      },
      response.status,
      true,
    );
  }
  if (typeof body.detail === "string" && body.detail) {
    const code = codeForStatus(response.status);
    return new StudioApiError(
      {
        code,
        message: body.detail,
        suggestion: SUGGESTION_FOR_CODE[code],
        retryable: retryableForCode(code),
      },
      response.status,
      false,
    );
  }
  const described = describeStatus(response.status);
  return new StudioApiError(described, response.status, false);
}

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(apiUrl(path), { headers: { Accept: "application/json" } });
  if (!response.ok) {
    const error = await studioError(response);
    recordStudioError(error.error, path);
    throw error;
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
    const error = await studioError(response);
    recordStudioError(error.error, path);
    throw error;
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
    const error = await studioError(response);
    recordStudioError(error.error, path);
    throw error;
  }
  return (await response.json()) as T;
}

async function withLocal<T>(
  sidecar: () => Promise<T>,
  local: (bff: Awaited<ReturnType<typeof getStudioBff>>) => Promise<T>,
): Promise<T> {
  try {
    return await sidecar();
  } catch (error) {
    // Application failures from the sidecar are real failures; only transport
    // failures fall through to the local BFF.
    if (!isTransportFailure(error)) {
      throw error;
    }
    const bff = await getStudioBff();
    return local(bff);
  }
}

export async function fetchConfig(): Promise<StudioConfig> {
  const body = await getJson<{ defaults: StudioConfig }>("/api/config");
  return body.defaults;
}

export interface SidecarDiagnostics {
  version: string;
  python: string;
  db: {
    name: string;
    size_bytes: number;
    integrity: string;
    counts: { jobs: number; outcomes: number; evidence: number; observations: number };
  };
  migrations: Record<string, string>;
  capabilities: unknown[];
}

export function fetchDiagnostics(): Promise<SidecarDiagnostics> {
  return getJson<SidecarDiagnostics>("/api/diagnostics");
}

export function fetchChangelog(): Promise<ChangelogData> {
  return withLocal(
    () => getJson<ChangelogData>("/api/changelog"),
    (bff) => bff.fetchChangelog(),
  );
}

export async function fetchCanvas(mcpUrl: string): Promise<CanvasData> {
  return withLocal(
    () => getJson<CanvasData>(`/api/canvas?mcp_url=${encodeURIComponent(mcpUrl)}`),
    (bff) => bff.data.fetchCanvas(),
  );
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

/**
 * The model ids the configured backend serves.
 *
 * The sidecar asks, not the browser: the model server may be reachable only
 * from the host machine and is not necessarily CORS-open.
 */
export function fetchModels(config: {
  base_url: string;
  api_key: string;
}): Promise<ModelList> {
  return postJson<ModelList>("/api/models", config);
}

export function addStep(payload: AddStepPayload): Promise<Step> {
  return postJson<Step>("/api/steps", payload);
}

export function addOutcome(payload: AddOutcomePayload): Promise<Outcome> {
  return postJson<Outcome>("/api/outcomes", payload);
}

export function createJob(payload: CreateJobPayload): Promise<Job> {
  return postJson<Job>("/api/jobs", payload);
}

export function updateJob(
  jobId: string,
  payload: { name?: string; description?: string; mcp_url: string },
): Promise<Job> {
  return sendJson<Job>("PATCH", `/api/jobs/${encodeURIComponent(jobId)}`, payload);
}

export function deleteJob(jobId: string, mcpUrl: string): Promise<{ deleted: string }> {
  return deleteJson<{ deleted: string }>(
    `/api/jobs/${encodeURIComponent(jobId)}?mcp_url=${encodeURIComponent(mcpUrl)}`,
  );
}

export function updateStep(
  stepId: string,
  payload: { name?: string; order?: number; mcp_url: string },
): Promise<Step> {
  return sendJson<Step>("PATCH", `/api/steps/${encodeURIComponent(stepId)}`, payload);
}

export function deleteStep(stepId: string, mcpUrl: string): Promise<{ deleted: string }> {
  return deleteJson<{ deleted: string }>(
    `/api/steps/${encodeURIComponent(stepId)}?mcp_url=${encodeURIComponent(mcpUrl)}`,
  );
}

export function updateOutcome(
  outcomeId: string,
  payload: { statement?: string; importance?: number; satisfaction?: number; mcp_url: string },
): Promise<Outcome> {
  return sendJson<Outcome>(
    "PATCH",
    `/api/outcomes/${encodeURIComponent(outcomeId)}`,
    payload,
  );
}

export function deleteOutcome(outcomeId: string, mcpUrl: string): Promise<{ deleted: string }> {
  return deleteJson<{ deleted: string }>(
    `/api/outcomes/${encodeURIComponent(outcomeId)}?mcp_url=${encodeURIComponent(mcpUrl)}`,
  );
}

export function fetchConnectorCatalog(): Promise<ConnectorPreset[]> {
  return getJson<ConnectorPreset[]>("/api/connectors/catalog");
}

export function fetchConnectors(): Promise<ConnectorListItem[]> {
  return getJson<ConnectorListItem[]>("/api/connectors");
}

/**
 * Search the marketplace. `area` and `q` are server-side filters so a narrow
 * query does not depend on the page having fetched everything first.
 */
export async function fetchMarketplace(params: {
  q?: string;
  area?: string;
  limit?: number;
} = {}): Promise<MarketplaceSearch> {
  const search = new URLSearchParams();
  if (params.q) search.set("q", params.q);
  if (params.area) search.set("area", params.area);
  if (params.limit) search.set("limit", String(params.limit));
  const suffix = search.toString();
  return normalizeMarketplace(
    await getJson<Partial<MarketplaceSearch>>(
      `/api/marketplace/servers${suffix ? `?${suffix}` : ""}`,
    ),
  );
}

/** Editor's picks: the curated presets, recommended first. */
export async function fetchFeatured(limit = 6): Promise<MarketplaceSearch> {
  return normalizeMarketplace(
    await getJson<Partial<MarketplaceSearch>>(`/api/marketplace/featured?limit=${limit}`),
  );
}

/**
 * The local BFF fallback may answer with a subset of the search shape, so a
 * missing list becomes an empty one here rather than an undefined that callers
 * would have to guard at every read.
 */
function normalizeMarketplace(body: Partial<MarketplaceSearch>): MarketplaceSearch {
  return {
    listings: body.listings ?? [],
    areas: body.areas ?? {},
    cached: body.cached ?? false,
    types: body.types ?? [],
  };
}

export function addConnector(payload: AddConnectorPayload): Promise<ConnectorOperationResponse> {
  return postJson<ConnectorOperationResponse>("/api/connectors", payload);
}

export async function deleteConnector(name: string): Promise<ConnectorOperationResponse> {
  const response = await fetch(apiUrl(`/api/connectors/${encodeURIComponent(name)}`), {
    method: "DELETE",
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    const error = await studioError(response);
    recordStudioError(error.error, `/api/connectors/${encodeURIComponent(name)}`);
    throw error;
  }
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
  try {
    const response = await fetch(apiUrl("/api/chat"), {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify({
        ...request,
        messages: request.messages.reduce<{
          id: string;
          role: "user" | "assistant";
          content: string;
          parent_id: string | null;
        }[]>((history, message) => {
          if (message.role === "notice") {
            return history;
          }
          const parent_id = history.at(-1)?.id ?? null;
          history.push({
            id: message.id,
            role: message.role,
            content: message.content,
            parent_id,
          });
          return history;
        }, []),
        attachments: request.attachments?.map((attachment) => ({
          name: attachment.name,
          content_type: attachment.contentType,
          size: attachment.size,
          ...(attachment.text ? { text: attachment.text } : {}),
          ...(attachment.dataUrl ? { data_url: attachment.dataUrl } : {}),
        })),
      }),
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
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") {
      throw error;
    }
    if (!isTransportFailure(error)) {
      throw error;
    }
    const bff = await getStudioBff();
    await bff.chat.stream(request, onEvent, signal);
  }
}


/**
 * The signal inbox. Signals live in the shared store, so the CLI and the Studio
 * read the same feed; there is no browser-side copy to diverge into.
 */
export async function fetchSignals(
  mcpUrl: string,
  options: { unreadOnly?: boolean; limit?: number } = {},
): Promise<Signal[]> {
  const params = new URLSearchParams({ mcp_url: mcpUrl });
  if (options.unreadOnly) {
    params.set("unread_only", "true");
  }
  if (options.limit !== undefined) {
    params.set("limit", String(options.limit));
  }
  return getJson<Signal[]>(`/api/signals?${params.toString()}`);
}

export async function fetchUnreadSignalCount(mcpUrl: string): Promise<number> {
  const body = await getJson<{ count: number }>(
    `/api/signals/unread-count?mcp_url=${encodeURIComponent(mcpUrl)}`,
  );
  return body.count;
}

export async function markSignalRead(signalId: string, mcpUrl: string): Promise<Signal> {
  return sendJson<Signal>("POST", `/api/signals/${encodeURIComponent(signalId)}/read`, {
    mcp_url: mcpUrl,
  });
}

export async function dismissSignal(signalId: string, mcpUrl: string): Promise<Signal> {
  return sendJson<Signal>("POST", `/api/signals/${encodeURIComponent(signalId)}/dismiss`, {
    mcp_url: mcpUrl,
  });
}

export async function fetchSegments(mcpUrl: string, jobId?: string): Promise<Segment[]> {
  const params = new URLSearchParams({ mcp_url: mcpUrl });
  if (jobId) {
    params.set("job_id", jobId);
  }
  return getJson<Segment[]>(`/api/segments?${params.toString()}`);
}

/** The recorded Stage 6 path, or null when no strategy has been proposed yet. */
export async function fetchStrategy(mcpUrl: string): Promise<Strategy | null> {
  const params = new URLSearchParams({ mcp_url: mcpUrl });
  return getJson<Strategy | null>(`/api/strategy?${params.toString()}`);
}

export async function proposeStrategy(mcpUrl: string, jobId?: string): Promise<Strategy> {
  return sendJson<Strategy>("POST", "/api/strategy/propose", {
    mcp_url: mcpUrl,
    job_id: jobId ?? null,
  });
}


export async function fetchMemory(): Promise<Observation[]> {
  return withLocal(
    () =>
      getJson<{ observations: Observation[] }>("/api/memory/observations").then(
        (body) => body.observations,
      ),
    (bff) => bff.memory.listObservations(),
  );
}

export interface AddObservationPayload {
  kind: ObservationKind;
  text: string;
  data?: Record<string, unknown>;
  confidence?: number;
  confirmed?: boolean;
}

export async function addObservation(payload: AddObservationPayload): Promise<Observation> {
  return withLocal(
    () =>
      postJson<{ observation: Observation }>("/api/memory/observations", payload).then(
        (body) => body.observation,
      ),
    (bff) => bff.memory.addObservation(payload),
  );
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
  return withLocal(
    () =>
      sendJson<{ observation: Observation }>(
        "PATCH",
        `/api/memory/observations/${encodeURIComponent(observationId)}`,
        payload,
      ).then((body) => body.observation),
    (bff) => bff.memory.updateObservation(observationId, payload),
  );
}

export function deleteObservation(observationId: string): Promise<{ ok: boolean }> {
  return withLocal(
    () =>
      deleteJson<{ ok: boolean }>(
        `/api/memory/observations/${encodeURIComponent(observationId)}`,
      ),
    async (bff) => bff.memory.deleteObservation(observationId),
  );
}

export function clearMemory(): Promise<{ ok: boolean }> {
  return withLocal(
    () => deleteJson<{ ok: boolean }>("/api/memory"),
    async (bff) => bff.memory.clearMemory(),
  );
}

/** Every thread the PM can reopen, most recently touched first. */
export async function listConversations(): Promise<ConversationSummary[]> {
  return withLocal(
    () =>
      getJson<{ conversations: ConversationSummary[] }>("/api/conversations").then(
        (body) => body.conversations,
      ),
    (bff) => bff.memory.listConversations(),
  );
}

/**
 * The thread to reopen when the page opens. Server-first, but an exchange this
 * browser streamed from its own model is in no server row, so it wins when it
 * is the more recent work — otherwise the person who used the browser model
 * reloads onto last week's thread and wonders where their answer went.
 */
export async function fetchLatestConversation(): Promise<LatestConversation> {
  const server = await withLocal(
    () => getJson<LatestConversation>("/api/conversations/latest"),
    (bff) => bff.memory.latestConversation(),
  );
  let mine: LatestConversation | null;
  try {
    mine = await browserAnsweredThread();
  } catch {
    return server;
  }
  if (!mine?.conversation) {
    return server;
  }
  if (!server.conversation) {
    return mine;
  }
  return touchedAfter(mine.conversation.updated_at, server.conversation.updated_at)
    ? mine
    : server;
}

/**
 * The newest thread this browser holds an answer for, if it holds one at all.
 * A local draft written while the server was out is not this claim: only the
 * reply the browser's own model produced is work the server cannot show.
 */
async function browserAnsweredThread(): Promise<LatestConversation | null> {
  const bff = await getStudioBff();
  const latest = await bff.memory.latestConversation();
  const { conversation } = latest;
  if (!conversation) {
    return null;
  }
  const recorded = await readEdgeTurns(bff.memory, conversation.id);
  if (!recorded.some((turn) => turn.provenance === "edge")) {
    return null;
  }
  return { ...latest, conversation };
}

/** Wall-clock order, because the two producers stamp their own format. */
function touchedAfter(candidate: string, current: string): boolean {
  return Date.parse(candidate) > Date.parse(current);
}

/** The whole branch tree, so a reload reopens the branch that was visible. */
export async function fetchConversationTree(conversationId: string): Promise<ConversationTree> {
  const tree = await withLocal(
    () =>
      getJson<ConversationTree>(
        `/api/conversations/${encodeURIComponent(conversationId)}/tree`,
      ),
    (bff) => localTree(bff, conversationId),
  ).catch((failure: unknown) => {
    // A server that has never seen this id is not a dead end for the person
    // whose own browser wrote the thread: the browser's copy is the thread.
    if (!(failure instanceof StudioApiError) || failure.status !== 404) {
      throw failure;
    }
    return getStudioBff()
      .then((bff) => localTree(bff, conversationId))
      .catch(() => {
        // Neither copy exists, which is the 404 the server said it was.
        throw failure;
      });
  });
  return withBrowserTurns(tree, conversationId);
}

/** This browser's copy of a thread, in the shape the server would have sent. */
async function localTree(
  bff: Awaited<ReturnType<typeof getStudioBff>>,
  conversationId: string,
): Promise<ConversationTree> {
  const local = await bff.memory.conversationTree(conversationId);
  return {
    conversation: local.conversation,
    messages: local.messages.map((turn) => ({
      id: String(turn.message_id ?? turn.id),
      parent_id: turn.parent_id ?? null,
      role: turn.role,
      content: turn.content,
      created_at: turn.created_at,
      ...(turn.provenance ? { provenance: turn.provenance } : {}),
    })),
    head_id: local.head_id,
  };
}

/**
 * Turns this tab answered on its own are in no server row, so the server's tree
 * cannot show them. Read them from the browser's memory and merge; the person
 * who closed the tab and came back gets the thread they actually had.
 */
async function withBrowserTurns(
  tree: ConversationTree,
  conversationId: string,
): Promise<ConversationTree> {
  let mine: TurnNode[];
  try {
    const bff = await getStudioBff();
    mine = await readEdgeTurns(bff.memory, conversationId);
  } catch {
    // The server's thread is the one that must survive: a memory store that
    // will not open costs the person their own drafts, nothing more.
    return tree;
  }
  const known = new Set(tree.messages.map((turn) => turn.id));
  const missing = mine.filter((turn) => !known.has(turn.id));
  if (!missing.length) {
    return tree;
  }
  // Recorded order is the thread order; two turns stamped in the same
  // millisecond are normal when the model runs down the hall.
  const tip = missing[missing.length - 1];
  const head = tree.messages.find((turn) => turn.id === tree.head_id);
  return {
    ...tree,
    messages: [...tree.messages, ...missing],
    // A branch left open deliberately stays open; only a newer answer moves it.
    head_id: head && !touchedAfter(tip.created_at, head.created_at) ? tree.head_id : tip.id,
  };
}

/** One exchange this tab streamed, and the thread it was asked in — which a
 * first turn does not have yet. */
export interface BrowserExchange {
  conversationId: string | null;
  question: { id: string; text: string; parentId: string | null };
  answer: { id: string; text: string };
}

/**
 * Keep an exchange the browser answered for itself. No server ever saw it, so
 * this store is the only copy there is. Returns the conversation it landed in,
 * for a turn asked before the thread existed.
 */
export async function recordBrowserTurn(exchange: BrowserExchange): Promise<string> {
  const bff = await getStudioBff();
  const conversationId =
    exchange.conversationId ?? (await bff.memory.createConversation()).id;
  await recordEdgeTurn(bff.memory, {
    conversationId,
    question: exchange.question,
    answer: exchange.answer,
  });
  return conversationId;
}

/** Record which branch is visible. */
export async function setConversationHead(
  conversationId: string,
  headId: string | null,
): Promise<Conversation> {
  return withLocal(
    () =>
      sendJson<{ conversation: Conversation }>(
        "PATCH",
        `/api/conversations/${encodeURIComponent(conversationId)}`,
        { head_id: headId },
      ).then((body) => body.conversation),
    async (bff) => bff.memory.setConversationHead(conversationId, headId),
  );
}

/** Answer one paused write. The turn resumes on the stream it came from. */
export async function resolveApproval(
  approvalId: string,
  approved: boolean,
  reason = "",
): Promise<{ ok: boolean; id: string }> {
  return withLocal(
    () =>
      postJson<{ ok: boolean; id: string }>(
        `/api/approvals/${encodeURIComponent(approvalId)}`,
        { approved, reason },
      ),
    async () => ({ ok: true, id: approvalId }),
  );
}

export async function createConversation(): Promise<Conversation> {
  return withLocal(
    () =>
      postJson<{ conversation: Conversation }>("/api/conversations", {}).then(
        (body) => body.conversation,
      ),
    async (bff) => bff.memory.createConversation(),
  );
}

export function scheduleWork(payload: {
  name: string;
  schedule_expression: string;
  agent_id?: string;
  trigger_type?: string;
  payload?: Record<string, unknown>;
  job_id?: string;
  mcp_url: string;
}): Promise<{ ok: boolean; result: unknown }> {
  return postJson("/api/schedule", payload);
}

export function triggerScheduledWork(
  workId: string,
  mcpUrl: string,
): Promise<{ ok: boolean; result: unknown }> {
  return postJson(`/api/schedule/${encodeURIComponent(workId)}/trigger?mcp_url=${encodeURIComponent(mcpUrl)}`, {});
}

export function cancelScheduledWork(
  workId: string,
  mcpUrl: string,
): Promise<{ ok: boolean; result: unknown }> {
  return postJson(`/api/schedule/${encodeURIComponent(workId)}/cancel?mcp_url=${encodeURIComponent(mcpUrl)}`, {});
}

export function addEvidence(payload: {
  source_name: string;
  source_kind?: string;
  name: string;
  content: string;
  url?: string;
  item_type?: string;
  job_id?: string;
  step_id?: string;
  outcome_id?: string;
  mcp_url: string;
}): Promise<{ ok: boolean }> {
  return postJson<{ ok: boolean }>("/api/evidence", payload);
}

export function deleteEvidence(evidenceId: string, mcpUrl: string): Promise<{ ok: boolean }> {
  return deleteJson<{ ok: boolean }>(
    `/api/evidence/${encodeURIComponent(evidenceId)}?mcp_url=${encodeURIComponent(mcpUrl)}`,
  );
}

export function promoteEvidence(
  evidenceId: string,
  payload: {
    target: "job" | "outcome";
    job_id?: string;
    statement?: string;
    name?: string;
    importance?: number;
    satisfaction?: number;
    mcp_url: string;
  },
): Promise<{ ok: boolean }> {
  return postJson<{ ok: boolean }>(
    `/api/evidence/${encodeURIComponent(evidenceId)}/promote`,
    payload,
  );
}
