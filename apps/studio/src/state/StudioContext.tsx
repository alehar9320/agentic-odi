/* eslint-disable react-refresh/only-export-components -- context module intentionally exports the hook and constants alongside the provider */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import type {
  AppendMessage,
  ExternalThreadQueueAdapter,
  MessageQueueController,
} from "@assistant-ui/react";

import { focusLabel, focusPointer } from "../lib/focus";
import {
  addConnector as apiAddConnector,
  addObservation as apiAddObservation,
  addOutcome as apiAddOutcome,
  addStep as apiAddStep,
  asStudioError,
  clearMemory as apiClearMemory,
  createConversation as apiCreateConversation,
  createJob as apiCreateJob,
  deleteConnector as apiDeleteConnector,
  deleteJob as apiDeleteJob,
  deleteObservation as apiDeleteObservation,
  deleteEvidence as apiDeleteEvidence,
  deleteOutcome as apiDeleteOutcome,
  deleteStep as apiDeleteStep,
  dismissSignal as apiDismissSignal,
  fetchCanvas,
  fetchConfig,
  fetchConnectorCatalog,
  fetchConnectors,
  fetchConversationTree,
  fetchFeatured,
  fetchLatestConversation,
  fetchMarketplace,
  fetchMemory,
  fetchModels,
  fetchSegments,
  fetchSignals,
  fetchStrategy,
  fetchUnreadSignalCount,
  healthLlm,
  healthMcp,
  listConversations as apiListConversations,
  markSignalRead as apiMarkSignalRead,
  promoteEvidence as apiPromoteEvidence,
  resolveApproval as apiResolveApproval,
  setConversationHead as apiSetConversationHead,
  streamChat,
  updateJob as apiUpdateJob,
  updateObservation as apiUpdateObservation,
  updateOutcome as apiUpdateOutcome,
  updateStep as apiUpdateStep,
  type AddObservationPayload,
  type UpdateObservationPayload,
} from "../api/studioApi";
import type { RawSseEvent } from "../api/sse";
import { preparedAttachments } from "../assistant/attachments";
import { textOf } from "../assistant/convert";
import { createTurnQueue, queuedUserMessage } from "../assistant/queue";
import { textWithQuote, type ComposerQuote } from "../assistant/quote";
import { capabilityRegistry, type Capability } from "../bff/capabilities/registry";
import { deriveDeviceStatus, type DeviceStatus } from "./deviceStatus";
import { isOnline } from "../lib/onlineStatus";
import {
  PROBE_SETTINGS_DEBOUNCE_MS,
  createProbeScheduler,
  type ProbeScheduler,
} from "./scheduleProbe";
import {
  classifyProbeError,
  createProbeBreaker,
  type BreakerState,
  type ProbeBreaker,
  type ProbeOutcome,
} from "./probeBreaker";
import { clearSession, loadSession, saveSession, type StudioSession } from "../lib/session";
import type {
  AddConnectorPayload,
  AddOutcomePayload,
  AddStepPayload,
  CanvasData,
  CanvasState,
  ChatAttachment,
  ChatMessage,
  ChatPart,
  Claim,
  ClaimCitation,
  ClaimStatus,
  ConnectorListItem,
  ConnectorPreset,
  ConnectorSuggestion,
  ConversationSummary,
  CustomizeTarget,
  FocusSubject,
  MarketplaceListing,
  MarketplaceSearch,
  Observation,
  Segment,
  Signal,
  SignalSubjectKind,
  Strategy,
  StudioBrief,
  StudioConfig,
  StudioError,
  Thesis,
  ToolStatus,
  TurnNode,
  WorkspacePanelId,
} from "../types";
import { catalogManifest } from "../ui/catalog";
import { parseUiSpec } from "../ui/protocol";
import { recordStream, recordStudioError } from "../diagnostics/bundle";
import { SettingsProvider, useSettings, SETTINGS_KEY } from "./settings/SettingsContext";
import {
  NoticesProvider,
  useNoticesActions,
  type ToastKind,
} from "./notices/NoticesContext";

/**
 * The visible path of a persisted conversation: from the head back to the root.
 * Rows are ordered by insertion, so a legacy conversation with no head simply
 * resolves to its last turn.
 */
export function pathToHead(nodes: TurnNode[], headId: string | null): TurnNode[] {
  if (nodes.length === 0) {
    return [];
  }
  const byId = new Map(nodes.map((node) => [node.id, node]));
  const leafId = headId && byId.has(headId) ? headId : nodes[nodes.length - 1].id;
  const path: TurnNode[] = [];
  const seen = new Set<string>();
  let current: string | null = leafId;
  while (current && byId.has(current) && !seen.has(current)) {
    seen.add(current);
    const node = byId.get(current) as TurnNode;
    path.push(node);
    current = node.parent_id;
  }
  return path.reverse();
}

/** Persisted turns as the thread renders them. */
export function turnsToMessages(
  nodes: TurnNode[],
  headId: string | null,
): ChatMessage[] {
  return pathToHead(nodes, headId).flatMap((node) => {
    if (node.role !== "user" && node.role !== "assistant") {
      return [];
    }
    const content = node.content ?? "";
    const claims = node.claims ?? [];
    return [
      {
        id: node.id,
        parentId: node.parent_id,
        role: node.role,
        content,
        parts: claims.length
          ? [{ kind: "claims" as const, content, claims }]
          : content
            ? [{ kind: "text" as const, text: content }]
            : [],
      },
    ];
  });
}

const CLAIM_STATUSES = new Set<ClaimStatus>(["cited", "hypothesis", "uncited"]);

/** The claims a terminal frame carries, read defensively. */
function readClaims(raw: unknown): Claim[] {
  if (!Array.isArray(raw)) {
    return [];
  }
  const claims: Claim[] = [];
  for (const item of raw) {
    if (!item || typeof item !== "object") {
      continue;
    }
    const candidate = item as Partial<Claim>;
    if (typeof candidate.index !== "number" || typeof candidate.text !== "string") {
      continue;
    }
    const evidence: ClaimCitation[] = [];
    for (const rawCitation of Array.isArray(candidate.evidence) ? candidate.evidence : []) {
      if (!rawCitation || typeof rawCitation !== "object") {
        continue;
      }
      const citation = rawCitation as Partial<ClaimCitation>;
      if (typeof citation.id !== "string" || !citation.id) {
        continue;
      }
      evidence.push({
        id: citation.id,
        name: typeof citation.name === "string" ? citation.name : citation.id,
        source_name: typeof citation.source_name === "string" ? citation.source_name : "",
      });
    }
    const status =
      typeof candidate.status === "string" && CLAIM_STATUSES.has(candidate.status as ClaimStatus)
        ? (candidate.status as ClaimStatus)
        : "uncited";
    claims.push({
      index: candidate.index,
      text: candidate.text,
      status,
      evidence,
      reason: typeof candidate.reason === "string" ? candidate.reason : null,
    });
  }
  return claims;
}

/** Read the failure the sidecar reported on an SSE `error` event. */
function readStudioError(raw: unknown): StudioError {
  if (raw && typeof raw === "object" && "code" in raw) {
    const error = raw as Partial<StudioError>;
    const parsed = {
      code: String(error.code ?? "internal"),
      message: String(error.message ?? "The assistant could not finish this turn."),
      detail: error.detail ?? null,
      suggestion: error.suggestion ?? null,
      retryable: Boolean(error.retryable),
      request_id: error.request_id ?? null,
    };
    recordStudioError(parsed, "/api/chat");
    return parsed;
  }
  const parsed: StudioError = {
    code: "internal",
    message: "The assistant could not finish this turn.",
    retryable: true,
  };
  recordStudioError(parsed, "/api/chat");
  return parsed;
}

const CANVAS_KEY = "studio.canvas";
const DISPLAY_NAME_KEY = "studio.displayName";
const BRIEF_KEY = "studio.brief";
const THESES_KEY = "studio.theses";

/** How often a focused window re-reads the signal inbox from the store. */
const SIGNAL_POLL_INTERVAL_MS = 60_000;

/** How long the studio waits before probing what it is connected to. */
const PROBE_IDLE_TIMEOUT_MS = 2_000;

/** The lens that can show a signal's subject. Unwired kinds navigate nowhere. */
const PANEL_FOR_SUBJECT: Partial<Record<SignalSubjectKind, WorkspacePanelId>> = {
  job: "jobmap",
  step: "jobmap",
  outcome: "landscape",
  evidence: "evidence",
  segment: "segments",
  strategy: "segments",
};

export function writeReceipt(record: unknown, acknowledged: string): string {
  const pending = (record as { pending?: boolean } | null | undefined)?.pending === true;
  return pending ? "Saved on this device · will sync" : acknowledged;
}

/**
 * What `startNewThread()` hands back: the snapshot lives in a ref, so the only
 * way to reach it is through the handle that took it.
 */
export interface NewThreadHandle {
  undo: () => void;
  commit: () => void;
}

interface ThreadSnapshot {
  messages: ChatMessage[];
  conversationId: string | null;
  toolActivity: ToolActivity[];
  offlineReplyFor: string | null;
  scrollTop: number;
  undoToastId: number;
}

/**
 * The thread's scroll box, owned by the assistant-ui viewport primitive in
 * `ChatStage`. Undo restores a transcript the way the person left it, and the
 * reading position is part of what they left; the store has no other handle on
 * it, so the snapshot reaches for the one element the thread scrolls in.
 */
const THREAD_VIEWPORT_SELECTOR = ".chat__scroll";

export interface ToolActivity {
  name: string;
  status: string;
  preview?: string;
}

export interface ConnectionReport {
  sidecarReachable: boolean;
  mcpReachable: boolean;
  llmHealthy: boolean;
  llmMessage: string;
}

export interface StudioContextValue {
  settings: StudioConfig;
  saveSettings: (config: StudioConfig) => void;
  displayName: string;
  setDisplayName: (name: string) => void;
  brief: StudioBrief | null;
  saveBrief: (brief: StudioBrief) => void;
  /** True while the first-run context conversation is open. Never a modal. */
  setupOpen: boolean;
  openSetup: () => void;
  closeSetup: () => void;
  canvas: CanvasData | null;
  canvasLoading: boolean;
  canvasCached: boolean;
  /** What the canvas is: loading, ready, empty, or failed. */
  canvasState: CanvasState;
  /** The failure behind `canvasState.kind === "error"`, if any. */
  canvasError: StudioError | null;
  refreshCanvas: () => Promise<void>;
  llmHealth: { healthy: boolean | null; message: string };
  /**
   * What the probe breaker is doing (#536): `state` is `closed`, `open`,
   * `half-open`, or `degraded`, and `retryInMs` is how long until the next
   * probe is allowed. The bar reads this to say "Retrying in N min".
   */
  probeRetry: { state: BreakerState; retryInMs: number };
  /** Model ids the configured endpoint publishes. Empty means "type one". */
  models: string[];
  modelsLoading: boolean;
  /** Why the endpoint would not list models, if it would not. */
  modelsMessage: string | null;
  refreshModels: (config?: { base_url: string; api_key: string }) => Promise<void>;
  mcpReachable: boolean;
  sidecarReachable: boolean | null;
  /**
   * A store that failed its integrity check on boot. When set, the Studio
   * shows the failure page instead of a half-empty board: the database is the
   * only copy, so pretending it is empty would be a lie.
   */
  bootError: StudioError | null;
  /** Re-probe after a backup is restored; clears `bootError` on a clean answer. */
  recheckBoot: () => Promise<void>;
  /** Whether the user has dismissed this session's sidecar-down notice. */
  dismissedSidecarNotice: boolean;
  /** Probe again now, e.g. after the user started the sidecar. */
  recheckConnections: () => Promise<void>;
  dismissSidecarNotice: () => void;
  /** Probe the sidecar, MCP server, and model. Optionally against unsaved config. */
  checkConnections: (override?: Partial<StudioConfig>) => Promise<ConnectionReport>;
  /** Measure the same three connections for one panel, without changing what the studio believes. */
  surveyConnections: (override?: Partial<StudioConfig>) => Promise<ConnectionReport>;
  messages: ChatMessage[];
  streaming: boolean;
  thinkingPhase: string | null;
  toolActivity: ToolActivity[];
  /**
   * Enter a turn through the follow-up queue (#410): idle, it starts now;
   * mid-run, it waits its turn. The promise settles when the send is accepted,
   * not when the answer arrives.
   */
  sendMessage: (text: string, attachments?: ChatAttachment[]) => Promise<void>;
  /** Re-answer the turn that follows `messageId`, as a sibling branch. */
  regenerateFrom: (messageId: string | null) => Promise<void>;
  /** Replace the user turn before `messageId`, as a sibling branch. */
  editFrom: (messageId: string | null, text: string, attachments?: ChatAttachment[]) => Promise<void>;
  /** Take the branch the runtime switched to as the visible conversation. */
  switchBranch: (messages: ChatMessage[]) => void;
  /** Answer a paused write. The turn resumes on its own stream. */
  respondToApproval: (approvalId: string, approved: boolean, reason?: string) => Promise<void>;
  stopStreaming: () => void;
  /**
   * Follow-ups typed while a reply is running (#410): a quiet lane that runs
   * turns in order, never two streams at once. The composer renders it. Null
   * until the queue controller mounts.
   */
  queue: ExternalThreadQueueAdapter | null;
  clearChat: () => void;
  /**
   * Leave this thread behind without deleting it. Returns null when there is
   * nothing to leave, or when a reply is still coming and `stop` was not given
   * — the caller asks first.
   */
  startNewThread: (options?: { stop?: boolean }) => NewThreadHandle | null;
  conversationId: string | null;
  /** The recent threads, newest first, as the history list shows them. */
  conversations: ConversationSummary[];
  /** Re-read the history list; called when it opens and after a turn persists. */
  refreshConversations: () => Promise<void>;
  /** Open a past thread by loading its turns; never a conversation without them. */
  openConversation: (conversationId: string) => Promise<void>;
  memory: Observation[];
  memoryLoading: boolean;
  refreshMemory: () => Promise<void>;
  addObservation: (payload: AddObservationPayload) => Promise<Observation | null>;
  updateObservation: (
    observationId: string,
    payload: UpdateObservationPayload,
  ) => Promise<Observation | null>;
  deleteObservation: (observationId: string) => Promise<void>;
  clearMemory: () => Promise<void>;
  pushNotice: (text: string) => void;
  /**
   * The reply that no model produced, by message id — so the honest label sits on
   * the one answer it describes instead of every answer on screen.
   */
  offlineReplyFor: string | null;
  addStep: (payload: Omit<AddStepPayload, "mcp_url">) => Promise<void>;
  addOutcome: (payload: Omit<AddOutcomePayload, "mcp_url">) => Promise<void>;
  createJob: (payload: { name: string; description?: string }) => Promise<string | null>;
  updateJob: (jobId: string, payload: { name?: string; description?: string }) => Promise<void>;
  deleteJob: (jobId: string) => Promise<void>;
  updateStep: (stepId: string, payload: { name?: string; order?: number }) => Promise<void>;
  deleteStep: (stepId: string) => Promise<void>;
  updateOutcome: (
    outcomeId: string,
    payload: { statement?: string; importance?: number; satisfaction?: number },
  ) => Promise<void>;
  deleteOutcome: (outcomeId: string) => Promise<void>;
  deleteEvidence: (evidenceId: string) => Promise<void>;
  promoteEvidence: (
    evidenceId: string,
    payload: {
      target: "job" | "outcome";
      job_id?: string;
      statement?: string;
      name?: string;
      importance?: number;
      satisfaction?: number;
    },
  ) => Promise<void>;
  activePanel: WorkspacePanelId | null;
  openPanel: (panel: WorkspacePanelId) => void;
  closePanel: () => void;
  /** Close any open lens and hand the intent to the agent. One gesture. */
  ask: (intent: string) => void;
  pushToast: (
    kind: ToastKind,
    message: string,
    options?: { action?: { label: string; run: () => void }; durationMs?: number },
  ) => number;
  dismissToast: (id: number) => void;
  connectors: ConnectorListItem[];
  presets: ConnectorPreset[];
  /** The failure behind an unreachable connector catalog, if any. */
  presetError: StudioError | null;
  /** True while the connector catalog is being (re)read. */
  presetsLoading: boolean;
  /** The failure behind an unreachable connector list, if any. */
  connectorsError: StudioError | null;
  /** True while the installed connector list is being (re)read. */
  connectorsLoading: boolean;
  /** Probed availability of local and sidecar capabilities. */
  capabilities: Capability[];
  /** One answer for what works here, derived from `capabilities`. */
  deviceStatus: DeviceStatus;
  refreshConnectors: () => Promise<void>;
  refreshPresets: () => Promise<void>;
  refreshCapabilities: () => Promise<void>;
  addConnector: (payload: AddConnectorPayload) => Promise<void>;
  deleteConnector: (name: string) => Promise<void>;
  connectorSuggestions: string[];
  dismissConnectorSuggestion: (preset: string) => void;
  /** Whether the Customize page is on stage. */
  customizeOpen: boolean;
  /** Where Customize should land: a prefilled query, or one listing to focus. */
  customizeTarget: CustomizeTarget | null;
  openCustomize: (target?: CustomizeTarget) => void;
  closeCustomize: () => void;
  /** Marketplace results for the Customize page's current filters. */
  marketplace: MarketplaceSearch | null;
  marketplaceError: StudioError | null;
  marketplaceLoading: boolean;
  searchMarketplace: (params?: { q?: string; area?: string }) => Promise<void>;
  /** Editor's picks, fetched once per session. */
  featured: MarketplaceListing[];
  featuredError: StudioError | null;
  refreshFeatured: () => Promise<void>;
  installFromMarketplace: (listing: MarketplaceListing) => Promise<boolean>;
  /** The one connector the studio suggests next, or null when nothing applies. */
  connectorSuggestion: ConnectorSuggestion | null;
  dismissConnectorModal: () => void;
  /** Scored outcomes saved as shareable opportunity theses. */
  theses: Thesis[];
  saveThesis: (thesis: Omit<Thesis, "id" | "created_at">) => void;
  deleteThesis: (thesisId: string) => void;
  /** The inbox the store holds — not a browser copy of one. */
  signals: Signal[];
  unreadSignalCount: number;
  /** A failed inbox read must never read as "nothing happened". */
  signalsError: StudioError | null;
  refreshSignals: () => Promise<void>;
  markSignalAsRead: (id: string) => void;
  dismissSignal: (id: string) => void;
  /** Mark read, then open the lens on whatever the signal is about. */
  focusSignalSubject: (signal: Signal) => void;
  /** Point the studio at a subject and remember it for the next visit. */
  focusSubject: (kind: SignalSubjectKind, id: string) => void;
  /**
   * The one open-record path: focus a record and open the lens that shows it.
   * Every surface that names a record goes through here rather than inventing a
   * second navigation mechanism.
   */
  openRecord: (kind: SignalSubjectKind, id: string) => void;
  /** Stop speaking for the screen: forget the selection and the next visit's. */
  clearFocus: () => void;
  focusedSubject: FocusSubject | null;
  /** What the snapshot calls the focused record, or null when it cannot name it. */
  focusedSubjectLabel: string | null;
  /** Open the lens that holds the focused record, so the person can check it. */
  revealFocusedSubject: () => void;
  /** The job that owns the focused subject, so canvas panels can select it. */
  focusedJobId: string | null;
  /** Stage 5: the segments the scored outcomes support, read from the store. */
  segments: Segment[];
  /** Stage 6: the recorded path, or null when none has evidence yet. */
  strategy: Strategy | null;
  segmentsError: StudioError | null;
  refreshSegments: () => Promise<void>;
  /** The evidence record a citation chip asked the Evidence lens to show. */
  focusedEvidenceId: string | null;
  focusEvidence: (evidenceId: string) => void;
}

const StudioContext = createContext<StudioContextValue | null>(null);

/**
 * Whether an edit moved what the studio talks to. The theme is stored beside the
 * endpoints but is not one of them, so switching it must not trigger a probe.
 */
function settingsTargetsChanged(a: StudioConfig, b: StudioConfig): boolean {
  return (
    a.base_url !== b.base_url ||
    a.api_key !== b.api_key ||
    a.model_name !== b.model_name ||
    a.mcp_url !== b.mcp_url
  );
}

function loadFocusedSubject(): FocusSubject | null {
  const session = loadSession();
  if (!session) {
    return null;
  }
  if (session.job_id) {
    return { kind: "job", id: session.job_id };
  }
  if (session.step_id) {
    return { kind: "step", id: session.step_id };
  }
  if (session.outcome_id) {
    return { kind: "outcome", id: session.outcome_id };
  }
  return null;
}

function sessionForSubject(kind: SignalSubjectKind, id: string): StudioSession {
  return {
    job_id: kind === "job" ? id : null,
    step_id: kind === "step" ? id : null,
    outcome_id: kind === "outcome" ? id : null,
  };
}

function loadCanvasCache(): CanvasData | null {
  try {
    const raw = localStorage.getItem(CANVAS_KEY);
    if (raw) {
      return JSON.parse(raw) as CanvasData;
    }
  } catch {
    /* ignore malformed cache */
  }
  return null;
}

function loadDisplayName(): string {
  try {
    return localStorage.getItem(DISPLAY_NAME_KEY) ?? "";
  } catch {
    return "";
  }
}

function loadBrief(): StudioBrief | null {
  try {
    const raw = localStorage.getItem(BRIEF_KEY);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw) as Partial<StudioBrief>;
    const brief: StudioBrief = {
      product_name: String(parsed.product_name ?? ""),
      product_url: parsed.product_url ? String(parsed.product_url) : undefined,
      target_user: String(parsed.target_user ?? ""),
      job_statement: String(parsed.job_statement ?? ""),
      core_problem: String(parsed.core_problem ?? ""),
      role: parsed.role ? String(parsed.role) : undefined,
      team: parsed.team ? String(parsed.team) : undefined,
      evidence_at_hand: Array.isArray(parsed.evidence_at_hand)
        ? parsed.evidence_at_hand.map(String)
        : undefined,
      job_id: parsed.job_id ? String(parsed.job_id) : undefined,
      v2mom: parsed.v2mom,
    };
    return brief.product_name || brief.job_statement || brief.role ? brief : null;
  } catch {
    return null;
  }
}

function loadTheses(): Thesis[] {
  try {
    const raw = localStorage.getItem(THESES_KEY);
    if (raw) {
      return JSON.parse(raw) as Thesis[];
    }
  } catch {
    /* ignore malformed cache */
  }
  return [];
}

function StudioProviderInner({ children }: { children: ReactNode }) {
  const { settings, saveSettings: persistSettings } = useSettings();
  const {
    pushToast,
    dismissToast,
    setDismissedSidecarNotice,
    dismissedSidecarNotice,
  } = useNoticesActions();
  const [displayName, setDisplayNameState] = useState<string>(loadDisplayName);
  const [brief, setBrief] = useState<StudioBrief | null>(loadBrief);
  // The context conversation is never a gate. It opens from the stage, from a
  // hint once the studio has answered something, from /start, or from Settings.
  const [setupOpen, setSetupOpen] = useState(false);
  const [offlineReplyFor, setOfflineReplyFor] = useState<string | null>(null);
  const [canvasState, setCanvasState] = useState<CanvasState>(() => {
    const cached = loadCanvasCache();
    return cached ? { kind: "loading", data: cached } : { kind: "loading", data: null };
  });
  const [canvasCached, setCanvasCached] = useState(() => loadCanvasCache() !== null);
  const [llmHealth, setLlmHealth] = useState<{ healthy: boolean | null; message: string }>({
    healthy: null,
    message: "Health not checked yet.",
  });
  /**
   * What the probe breaker is doing (#536): whether an endpoint has stopped
   * answering, and how long until the next probe is allowed. The bar reads this
   * to say "Retrying in N min" instead of showing a spinner forever.
   */
  const [probeRetry, setProbeRetry] = useState<{ state: BreakerState; retryInMs: number }>({
    state: "closed",
    retryInMs: 0,
  });
  const [models, setModels] = useState<string[]>([]);
  const [modelsLoading, setModelsLoading] = useState(false);
  const [modelsMessage, setModelsMessage] = useState<string | null>(null);
  const [mcpReachable, setMcpReachable] = useState(false);
  const [sidecarReachable, setSidecarReachable] = useState<boolean | null>(null);
  const [bootError, setBootError] = useState<StudioError | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [memory, setMemory] = useState<Observation[]>([]);
  const [memoryLoading, setMemoryLoading] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [thinkingPhase, setThinkingPhase] = useState<string | null>(null);
  const [toolActivity, setToolActivity] = useState<ToolActivity[]>([]);
  const [activePanel, setActivePanel] = useState<WorkspacePanelId | null>(null);
  const [connectors, setConnectors] = useState<ConnectorListItem[]>([]);
  const [presets, setPresets] = useState<ConnectorPreset[]>([]);
  const [presetError, setPresetError] = useState<StudioError | null>(null);
  const [presetsLoading, setPresetsLoading] = useState(false);
  const [connectorsError, setConnectorsError] = useState<StudioError | null>(null);
  const [connectorsLoading, setConnectorsLoading] = useState(false);
  const [capabilities, setCapabilities] = useState<Capability[]>([]);
  const [capabilitiesCheckedAt, setCapabilitiesCheckedAt] = useState<string | null>(null);
  const [connectorSuggestions, setConnectorSuggestions] = useState<string[]>([]);
  const [serverSignals, setServerSignals] = useState<Signal[]>([]);
  const [unreadSignalCount, setUnreadSignalCount] = useState(0);
  const [signalsError, setSignalsError] = useState<StudioError | null>(null);
  const [segments, setSegments] = useState<Segment[]>([]);
  const [strategy, setStrategy] = useState<Strategy | null>(null);
  const [segmentsError, setSegmentsError] = useState<StudioError | null>(null);
  const [focusedSubject, setFocusedSubject] = useState<FocusSubject | null>(loadFocusedSubject);
  const [focusedEvidenceId, setFocusedEvidenceId] = useState<string | null>(null);
  const [customizeOpen, setCustomizeOpen] = useState(false);
  const [customizeTarget, setCustomizeTarget] = useState<CustomizeTarget | null>(null);
  const [marketplace, setMarketplace] = useState<MarketplaceSearch | null>(null);
  const [marketplaceError, setMarketplaceError] = useState<StudioError | null>(null);
  const [marketplaceLoading, setMarketplaceLoading] = useState(false);
  const marketplaceSeq = useRef(0);
  const [featured, setFeatured] = useState<MarketplaceListing[]>([]);
  const [featuredError, setFeaturedError] = useState<StudioError | null>(null);
  const [connectorModalDismissed, setConnectorModalDismissed] = useState(false);
  const [theses, setTheses] = useState<Thesis[]>(loadTheses);
  const abortRef = useRef<AbortController | null>(null);
  /** The id of the newest turn on the wire; a steered cut-in takes it over (#410). */
  const liveTurnId = useRef<string | null>(null);
  /** The deferred connectivity probe, until the person speaks or the view unmounts. */
  const idleProbeRef = useRef<{ cancel: () => void } | null>(null);
  /**
   * The one thing that decides when the next probe runs. It reschedules itself
   * from each result, so a refusal widens the gap and a wake does not stack a
   * second timer on top of the first (#535).
   */
  const probeSchedulerRef = useRef<ProbeScheduler | null>(null);
  /**
   * The single-flight breaker every probe shares (#536): one probe on the wire
   * at a time, and no probe at all while an endpoint keeps refusing.
   */
  const probeBreakerRef = useRef<ProbeBreaker | null>(null);
  if (probeBreakerRef.current === null) {
    probeBreakerRef.current = createProbeBreaker();
  }

  /** Publish the breaker's state so the bar can show a countdown while it is open. */
  const publishProbeRetry = useCallback(() => {
    const breaker = probeBreakerRef.current!;
    setProbeRetry({ state: breaker.state(), retryInMs: breaker.retryInMs() });
  }, []);
  /** What a scheduled probe should run, kept current without re-creating the timer. */
  const probeNowRef = useRef<() => Promise<boolean>>(async () => false);
  /** Runs the debounced probe a connection-setting edit earns. */
  const settingsProbeRef = useRef<() => void>(() => {});
  /** The pending settings edit, so a burst of keystrokes earns one probe. */
  const settingsProbeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  /** The last written settings, so an edit can be compared without a stale closure. */
  const settingsRef = useRef(settings);

  const signals = useMemo(
    () => [...serverSignals].sort((a, b) => (a.created_at < b.created_at ? 1 : -1)),
    [serverSignals],
  );

  const refreshSignals = useCallback(async () => {
    try {
      const [feed, unread] = await Promise.all([
        fetchSignals(settings.mcp_url, { limit: 50 }),
        fetchUnreadSignalCount(settings.mcp_url),
      ]);
      setServerSignals(feed);
      setUnreadSignalCount(unread);
      setSignalsError(null);
    } catch (error) {
      // Keep the last feed on screen: a failed read is not an empty inbox.
      setSignalsError(asStudioError(error));
    }
  }, [settings.mcp_url]);

  /**
   * Stages 5 and 6 read as one lens: the segments and the bet they imply. A
   * failed read keeps the last answer on screen rather than showing an empty
   * board, which would read as "the evidence says nothing".
   */
  const refreshSegments = useCallback(async () => {
    try {
      const [nextSegments, nextStrategy] = await Promise.all([
        fetchSegments(settings.mcp_url),
        fetchStrategy(settings.mcp_url),
      ]);
      setSegments(nextSegments);
      setStrategy(nextStrategy);
      setSegmentsError(null);
    } catch (error) {
      setSegmentsError(asStudioError(error));
    }
  }, [settings.mcp_url]);

  /**
   * The one connector the studio offers next. An agent suggestion wins, since
   * it is grounded in what the user just asked for; otherwise a studio with no
   * connectors at all points at its first Editor's pick, because a thin studio
   * is the other way users learn connectors exist.
   */
  const connectorSuggestion = useMemo<ConnectorSuggestion | null>(() => {
    if (connectorModalDismissed || customizeOpen) {
      return null;
    }
    const suggested = connectorSuggestions[0];
    if (suggested) {
      const match = featured.find(
        (item) => item.name === suggested || item.title === suggested || item.id === suggested,
      );
      return { id: suggested, listing: match ?? null, reason: "agent" };
    }
    if (connectors.length === 0 && featured.length > 0) {
      return { id: featured[0].id, listing: featured[0], reason: "empty" };
    }
    return null;
  }, [connectorModalDismissed, connectorSuggestions, connectors, customizeOpen, featured]);

  const markSignalAsRead = useCallback(
    (id: string) => {
      apiMarkSignalRead(id, settings.mcp_url)
        .then(refreshSignals)
        .catch((error) => setSignalsError(asStudioError(error)));
    },
    [refreshSignals, settings.mcp_url],
  );

  const dismissSignal = useCallback(
    (id: string) => {
      apiDismissSignal(id, settings.mcp_url)
        .then(refreshSignals)
        .catch((error) => setSignalsError(asStudioError(error)));
    },
    [refreshSignals, settings.mcp_url],
  );


  const threadSnapshot = useRef<ThreadSnapshot | null>(null);

  /** Put the thread back exactly as the snapshot left it, and stop offering Undo. */
  const undoNewThread = useCallback(() => {
    const snapshot = threadSnapshot.current;
    if (!snapshot) {
      return;
    }
    threadSnapshot.current = null;
    dismissToast(snapshot.undoToastId);
    setMessages(snapshot.messages);
    setConversationId(snapshot.conversationId);
    setToolActivity(snapshot.toolActivity);
    setOfflineReplyFor(snapshot.offlineReplyFor);
    const viewport = document.querySelector<HTMLElement>(THREAD_VIEWPORT_SELECTOR);
    if (viewport) {
      viewport.scrollTop = snapshot.scrollTop;
    }
  }, [dismissToast]);

  /**
   * The new thread is in use, so the snapshot is stale. Handing it back now
   * would splice two threads together, which is worse than no Undo at all.
   */
  const commitNewThread = useCallback(() => {
    const snapshot = threadSnapshot.current;
    if (!snapshot) {
      return;
    }
    threadSnapshot.current = null;
    dismissToast(snapshot.undoToastId);
    pushToast("info", "New thread started.");
  }, [dismissToast, pushToast]);

  const startNewThread = useCallback(
    (options?: { stop?: boolean }) => {
      if (streaming) {
        if (!options?.stop) {
          return null;
        }
      } else if (messages.length === 0) {
        return null;
      }

      const viewport = document.querySelector<HTMLElement>(THREAD_VIEWPORT_SELECTOR);
      threadSnapshot.current = {
        messages,
        conversationId,
        toolActivity,
        offlineReplyFor,
        scrollTop: viewport?.scrollTop ?? 0,
        undoToastId: 0,
      };

      abortRef.current?.abort();
      abortRef.current = null;
      setMessages([]);
      setToolActivity([]);
      setStreaming(false);
      setThinkingPhase(null);
      setOfflineReplyFor(null);
      // Not `apiCreateConversation`: the sidecar names the conversation on the
      // `conversation` frame of the first reply, so a thread nobody wrote to
      // never becomes a row in the store — and never becomes what boot restores.
      setConversationId(null);

      const handle: NewThreadHandle = { undo: undoNewThread, commit: commitNewThread };
      threadSnapshot.current.undoToastId = pushToast(
        "success",
        "New thread. Your last one is still saved.",
        {
          durationMs: 10_000,
          action: { label: "Undo", run: () => handle.undo() },
        },
      );
      return handle;
    },
    [
      streaming,
      messages,
      conversationId,
      toolActivity,
      offlineReplyFor,
      pushToast,
      undoNewThread,
      commitNewThread,
    ],
  );


  const dismissConnectorSuggestion = useCallback((preset: string) => {
    setConnectorSuggestions((prev) => prev.filter((s) => s !== preset));
  }, []);

  const refreshConnectors = useCallback(async () => {
    setConnectorsError(null);
    setConnectorsLoading(true);
    try {
      setConnectors(await fetchConnectors());
    } catch (error) {
      // A list that could not be fetched is not an empty list.
      setConnectorsError(asStudioError(error));
      setConnectors([]);
    } finally {
      setConnectorsLoading(false);
    }
  }, []);

  const refreshPresets = useCallback(async () => {
    setPresetError(null);
    setPresetsLoading(true);
    try {
      setPresets(await fetchConnectorCatalog());
    } catch (error) {
      // An unreachable catalog is a failure, not an empty catalog: the settings
      // panel says so instead of offering a select with nothing in it.
      setPresetError(asStudioError(error));
      setPresets([]);
    } finally {
      setPresetsLoading(false);
    }
  }, []);

  const refreshCapabilities = useCallback(async () => {
    try {
      setCapabilities(await capabilityRegistry.statuses(settings));
      setCapabilitiesCheckedAt(new Date().toISOString());
    } catch {
      /* Capability probes are advisory; a probe failure leaves the list empty. */
      setCapabilities([]);
    }
  }, [settings]);

  /**
   * Ask the configured endpoint what it serves. A provider that will not list
   * models is not an error: the UI keeps the manual name and shows the reason.
   */
  const refreshModels = useCallback(
    async (config?: { base_url: string; api_key: string }) => {
      const target = config ?? { base_url: settings.base_url, api_key: settings.api_key };
      setModelsLoading(true);
      try {
        const result = await fetchModels(target);
        setModels(result.models);
        setModelsMessage(result.error);
      } catch (error) {
        setModels([]);
        setModelsMessage(asStudioError(error).message);
      } finally {
        setModelsLoading(false);
      }
    },
    [settings.base_url, settings.api_key],
  );

  const addConnector = useCallback(
    async (payload: AddConnectorPayload) => {
      try {
        const response = await apiAddConnector(payload);
        if (response.ok) {
          pushToast("success", `Added connector ${response.name}`);
        }
        await refreshConnectors();
      } catch (error) {
        pushToast("error", `Error adding connector: ${(error as Error).message}`);
      }
    },
    [pushToast, refreshConnectors],
  );

  const deleteConnector = useCallback(
    async (name: string) => {
      try {
        const response = await apiDeleteConnector(name);
        if (response.ok) {
          pushToast("success", `Removed connector ${response.name}`);
        }
        await refreshConnectors();
      } catch (error) {
        pushToast("error", `Error removing connector: ${(error as Error).message}`);
      }
    },
    [pushToast, refreshConnectors],
  );

  const refreshFeatured = useCallback(async () => {
    setFeaturedError(null);
    try {
      setFeatured((await fetchFeatured(6)).listings);
    } catch (error) {
      // An unreachable shelf is a failure, not an empty shelf.
      setFeaturedError(asStudioError(error));
      setFeatured([]);
    }
  }, []);

  const searchMarketplace = useCallback(async (params: { q?: string; area?: string } = {}) => {
    // A slower earlier request must not overwrite a newer one's results.
    const seq = ++marketplaceSeq.current;
    setMarketplaceLoading(true);
    setMarketplaceError(null);
    try {
      const result = await fetchMarketplace({ q: params.q, area: params.area, limit: 50 });
      if (seq !== marketplaceSeq.current) return;
      setMarketplace(result);
    } catch (error) {
      if (seq !== marketplaceSeq.current) return;
      setMarketplaceError(asStudioError(error));
      setMarketplace(null);
    } finally {
      if (seq === marketplaceSeq.current) setMarketplaceLoading(false);
    }
  }, []);

  const openCustomize = useCallback((target?: CustomizeTarget) => {
    setCustomizeTarget(target ?? null);
    setCustomizeOpen(true);
  }, []);

  const closeCustomize = useCallback(() => {
    setCustomizeOpen(false);
    setCustomizeTarget(null);
  }, []);

  const installFromMarketplace = useCallback(
    async (listing: MarketplaceListing) => {
      try {
        const response = await apiAddConnector({ marketplace_id: listing.id });
        if (response.ok) {
          pushToast("success", `Added connector ${response.name}`);
        }
        await refreshConnectors();
        return true;
      } catch (error) {
        pushToast("error", `Error adding connector: ${(error as Error).message}`);
        return false;
      }
    },
    [pushToast, refreshConnectors],
  );

  const dismissConnectorModal = useCallback(() => setConnectorModalDismissed(true), []);

  const saveThesis = useCallback((thesis: Omit<Thesis, "id" | "created_at">) => {
    const saved: Thesis = {
      ...thesis,
      id: `THESIS-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
      created_at: new Date().toISOString(),
    };
    setTheses((prev) => {
      const next = [saved, ...prev];
      try {
        localStorage.setItem(THESES_KEY, JSON.stringify(next));
      } catch {
        /* storage unavailable */
      }
      return next;
    });
  }, []);

  const deleteThesis = useCallback((thesisId: string) => {
    setTheses((prev) => {
      const next = prev.filter((thesis) => thesis.id !== thesisId);
      try {
        localStorage.setItem(THESES_KEY, JSON.stringify(next));
      } catch {
        /* storage unavailable */
      }
      return next;
    });
  }, []);

  const saveSettings = useCallback(
    (config: StudioConfig) => {
      // Only an edit that changes what the studio talks to is worth a probe: a
      // theme change is a settings change too, but nothing about a connection
      // moved, so it earns nothing. The timer is debounced, so typing a URL —
      // many saves in a row — earns one probe once the typing stops.
      if (settingsTargetsChanged(settingsRef.current, config)) {
        if (settingsProbeTimerRef.current !== null) {
          clearTimeout(settingsProbeTimerRef.current);
        }
        settingsProbeTimerRef.current = setTimeout(() => {
          settingsProbeTimerRef.current = null;
          settingsProbeRef.current();
        }, PROBE_SETTINGS_DEBOUNCE_MS);
      }
      settingsRef.current = config;
      persistSettings(config);
    },
    [persistSettings],
  );

  const setDisplayName = useCallback((name: string) => {
    setDisplayNameState(name);
    try {
      localStorage.setItem(DISPLAY_NAME_KEY, name);
    } catch {
      /* storage unavailable */
    }
  }, []);

  const saveBrief = useCallback((next: StudioBrief) => {
    setBrief(next);
    setSetupOpen(false);
    try {
      localStorage.setItem(BRIEF_KEY, JSON.stringify(next));
    } catch {
      /* storage unavailable */
    }
  }, []);

  const openSetup = useCallback(() => {
    setActivePanel(null);
    setSetupOpen(true);
  }, []);

  const closeSetup = useCallback(() => {
    setSetupOpen(false);
  }, []);

  const pushNotice = useCallback((text: string) => {
    setMessages((prev) => [
      ...prev,
      {
        id: crypto.randomUUID(),
        parentId: prev.length ? prev[prev.length - 1].id : null,
        role: "notice",
        content: text,
      },
    ]);
  }, []);

  /**
   * Measure the sidecar, the MCP server, and the model, keeping the failure that
   * made a negative answer negative. The scheduled probe needs that failure to
   * tell a flaky network from a rejected key (#536); a panel does not.
   */
  const measureConnections = useCallback(
    async (
      override: Partial<StudioConfig> = {},
    ): Promise<{ report: ConnectionReport; failure: unknown }> => {
      const target = { ...settings, ...override };
      let failure: unknown = null;
      const noteFailure = (error: unknown) => {
        failure = failure ?? error;
      };
      const [sidecar, mcp, llm] = await Promise.all([
        fetchConfig()
          .then(() => true)
          .catch((error: unknown) => {
            noteFailure(error);
            return false;
          }),
        healthMcp(target.mcp_url)
          .then((result) => result.reachable)
          .catch((error: unknown) => {
            noteFailure(error);
            return false;
          }),
        healthLlm({
          base_url: target.base_url,
          api_key: target.api_key,
          model: target.model_name,
        }).catch((error: unknown) => {
          noteFailure(error);
          return {
            healthy: false,
            message: (error as Error).message || "The model did not answer.",
          };
        }),
      ]);
      void refreshCapabilities();
      return {
        report: {
          sidecarReachable: sidecar,
          mcpReachable: mcp,
          llmHealthy: llm.healthy,
          llmMessage: llm.message,
        },
        failure,
      };
    },
    [settings, refreshCapabilities],
  );

  /**
   * Measure the sidecar, the MCP server, and the model without recording the result.
   *
   * A panel that owes the person looking at it fresh numbers calls this. Nothing here
   * changes what the rest of the studio believes, so reading a settings panel cannot
   * turn into a red strip across the window about a connection nobody was using.
   */
  const surveyConnections = useCallback(
    async (override: Partial<StudioConfig> = {}): Promise<ConnectionReport> => {
      return (await measureConnections(override)).report;
    },
    [measureConnections],
  );

  /**
   * Record a survey's answer, and let the studio act on it.
   *
   * `mode` decides what a negative answer is allowed to do. "evidence" — what a
   * person gets when they asked, by pressing Recheck or walking the setup — records
   * the whole truth, including a refusal. "recovery" is for background work nobody
   * requested: it records a refusal only when the sidecar itself witnessed it, or
   * when it contradicts something the studio already believed, because that is a
   * thing that just broke mid-session.
   *
   * The reason is the first minute. A browser-only visitor has no sidecar and often
   * no model, which is the design working, not an outage — and a red strip that
   * appears on its own half a minute after the page loads blames their studio for
   * being offline when nothing they did needed it to be online.
   */
  const applyReport = useCallback(
    (report: ConnectionReport, mode: "evidence" | "recovery"): ConnectionReport => {
      const sidecar = report.sidecarReachable;
      const llm = { healthy: report.llmHealthy, message: report.llmMessage };

      if (sidecar) {
        setSidecarReachable(true);
      } else if (mode === "evidence") {
        setSidecarReachable(false);
      } else {
        setSidecarReachable((previous) => (previous === true ? false : previous));
      }
      setMcpReachable(report.mcpReachable);
      // A model that answers is always news. A model that does not is news only when
      // the sidecar took part in the check — the browser asks it to reach the model, so
      // a negative it reports is measured rather than guessed — or when we previously
      // believed the model was alive and it has since stopped. On a hosted first run the
      // sidecar is absent too, and its silence is not a message about the model.
      if (llm.healthy || mode === "evidence" || sidecar) {
        setLlmHealth(llm);
      } else {
        setLlmHealth((previous) => (previous.healthy === true ? llm : previous));
      }
      if (sidecar) {
        setDismissedSidecarNotice(false);
      }
      return report;
    },
    [setDismissedSidecarNotice],
  );

  /**
   * The browser has no network. Both the process and the model are unreachable
   * for a reason that is neither's fault, so the studio says so once and stops
   * asking until the network returns (#535).
   */
  const applyOffline = useCallback(() => {
    setSidecarReachable(false);
    setMcpReachable(false);
    setLlmHealth({ healthy: false, message: "No network" });
  }, []);

  /**
   * Probe the sidecar, MCP server, and model, and let the studio act on it.
   *
   * A probe a person asked for — Recheck, the setup walk, a settings edit —
   * restarts the cadence, because the endpoint they just changed is not the one
   * that kept failing.
   */
  /**
   * One measurement through the shared breaker: the probe joins whatever is
   * already on the wire, records the report for the caller, and classifies a
   * negative answer so the breaker knows whether a retry is worth making (#536).
   */
  const probeOnce = useCallback(
    async (
      override: Partial<StudioConfig>,
      mode: "evidence" | "recovery",
    ): Promise<ConnectionReport | null> => {
      const settled = await probeBreakerRef.current!.run(async () => {
        const { report, failure } = await measureConnections(override);
        applyReport(report, mode);
        return {
          outcome: (report.llmHealthy
            ? "success"
            : classifyProbeError(failure, report.llmMessage)) as ProbeOutcome,
          value: report,
        };
      });
      publishProbeRetry();
      // A joined probe returns the other caller's promise, whose report is the
      // one this call also wants: both measured the same endpoint. `null` means
      // the breaker refused, so nothing was measured and nothing is reported.
      return settled?.value ?? null;
    },
    [measureConnections, applyReport, publishProbeRetry],
  );

  const checkConnections = useCallback(
    async (
      override: Partial<StudioConfig> = {},
      mode: "evidence" | "recovery" = "evidence",
    ): Promise<ConnectionReport> => {
      // A person asking restarts the cadence and closes the breaker: the endpoint
      // they just edited is not the one that kept failing (#536). They still join
      // a probe already in flight rather than starting a second one.
      probeBreakerRef.current?.reset();
      const report = await probeOnce(override, mode);
      probeSchedulerRef.current?.reset();
      // `reset` cleared the breaker, so this probe was allowed to run.
      return report!;
    },
    [probeOnce],
  );

  // Re-probe after the user acted on the sidecar notice (e.g. started the
  // sidecar). Resolves once the report is in so the UI can stop showing "busy".
  const recheckConnections = useCallback(async () => {
    await checkConnections();
  }, [checkConnections]);

  /**
   * One scheduled probe: it records what it finds, and it reports back whether
   * the endpoint answered so the scheduler can widen or reset the gap. It does
   * not reset the cadence itself — only a person asking does that.
   *
   * The breaker wraps the measurement, so an overlapping tick joins the probe
   * already in flight and a streak of transport failures stops the requests
   * rather than repeating them (#536).
   */
  const scheduledProbe = useCallback(async (): Promise<boolean> => {
    if (!isOnline()) {
      applyOffline();
      return false;
    }
    const report = await probeOnce({}, "recovery");
    return report?.llmHealthy ?? false;
  }, [probeOnce, applyOffline]);

  // Keep the scheduler pointed at the freshest probe without ever re-creating
  // the timer: the ref is what the running scheduler reads on each tick.
  useEffect(() => {
    probeNowRef.current = scheduledProbe;
  }, [scheduledProbe]);

  /**
   * Give up the probe scheduled at boot. A person who is already talking does not
   * need the studio finishing its survey of what it can reach.
   */
  const cancelScheduledProbes = useCallback(() => {
    const handle = idleProbeRef.current;
    idleProbeRef.current = null;
    handle?.cancel();
  }, []);

  const dismissSidecarNotice = useCallback(() => {
    setDismissedSidecarNotice(true);
  }, [setDismissedSidecarNotice]);

  const refreshCanvas = useCallback(async () => {
    // The inbox is re-read alongside the board: every path that reaches this
    // function either just changed the store or is checking what changed, and
    // a canvas that fails to load must not leave the bell showing stale counts.
    void refreshSignals();
    // Segments and the strategy are the other things a turn can create, and the
    // rail counts them, so they are re-read on the same beat.
    void refreshSegments();
    setCanvasState((prev) => ({ kind: "loading", data: prev.data }));
    try {
      const data = await fetchCanvas(settings.mcp_url);
      const isEmpty = !data.jobs.length && !data.steps.length && !data.outcomes.length;
      setCanvasState({ kind: isEmpty ? "empty" : "ready", data });
      setCanvasCached(false);
      try {
        localStorage.setItem(CANVAS_KEY, JSON.stringify(data));
      } catch {
        /* storage unavailable */
      }
    } catch (error) {
      // A failed canvas is a failure, not an empty canvas: the studio shows
      // what went wrong instead of a zeroed-out board.
      const problem = asStudioError(error);
      setCanvasState((prev) => ({ kind: "error", error: problem, data: prev.data }));
    }
  }, [settings.mcp_url, refreshSignals, refreshSegments]);

  const addStep = useCallback(
    async (payload: Omit<AddStepPayload, "mcp_url">) => {
      try {
        const step = await apiAddStep({ ...payload, mcp_url: settings.mcp_url });
        pushToast("success", writeReceipt(step, "Step added to Job Map!"));
        await refreshCanvas();
      } catch (error) {
        pushToast("error", `Error adding step: ${(error as Error).message}`);
      }
    },
    [settings.mcp_url, pushToast, refreshCanvas],
  );

  const addOutcome = useCallback(
    async (payload: Omit<AddOutcomePayload, "mcp_url">) => {
      // The form that asked for this shows the failure where the user typed
      // it, so the error travels up instead of disappearing into a toast. A
      // transport failure does not travel up: the write is queued locally and
      // the receipt says where it lives.
      const outcome = await apiAddOutcome({ ...payload, mcp_url: settings.mcp_url });
      pushToast("success", writeReceipt(outcome, "Outcome captured successfully!"));
      await refreshCanvas();
    },
    [settings.mcp_url, pushToast, refreshCanvas],
  );

  const createJob = useCallback(
    async (payload: { name: string; description?: string }): Promise<string | null> => {
      const job = await apiCreateJob({ ...payload, mcp_url: settings.mcp_url });
      pushToast("success", writeReceipt(job, `Job created: ${payload.name}`));
      await refreshCanvas();
      return job.id ?? null;
    },
    [settings.mcp_url, pushToast, refreshCanvas],
  );

  const updateJob = useCallback(
    async (jobId: string, payload: { name?: string; description?: string }) => {
      try {
        const job = await apiUpdateJob(jobId, { ...payload, mcp_url: settings.mcp_url });
        pushToast("success", writeReceipt(job, "Job updated."));
        await refreshCanvas();
      } catch (error) {
        pushToast("error", `Could not update the job: ${(error as Error).message}`);
      }
    },
    [settings.mcp_url, pushToast, refreshCanvas],
  );

  const deleteJob = useCallback(
    async (jobId: string) => {
      try {
        const result = await apiDeleteJob(jobId, settings.mcp_url);
        pushToast("success", writeReceipt(result, "Job removed."));
        await refreshCanvas();
      } catch (error) {
        pushToast("error", `Could not remove the job: ${(error as Error).message}`);
      }
    },
    [settings.mcp_url, pushToast, refreshCanvas],
  );

  const updateStep = useCallback(
    async (stepId: string, payload: { name?: string; order?: number }) => {
      try {
        const step = await apiUpdateStep(stepId, { ...payload, mcp_url: settings.mcp_url });
        pushToast("success", writeReceipt(step, "Step updated."));
        await refreshCanvas();
      } catch (error) {
        pushToast("error", `Could not update the step: ${(error as Error).message}`);
      }
    },
    [settings.mcp_url, pushToast, refreshCanvas],
  );

  const deleteStep = useCallback(
    async (stepId: string) => {
      try {
        const result = await apiDeleteStep(stepId, settings.mcp_url);
        pushToast("success", writeReceipt(result, "Step removed."));
        await refreshCanvas();
      } catch (error) {
        pushToast("error", `Could not remove the step: ${(error as Error).message}`);
      }
    },
    [settings.mcp_url, pushToast, refreshCanvas],
  );

  const updateOutcome = useCallback(
    async (
      outcomeId: string,
      payload: { statement?: string; importance?: number; satisfaction?: number },
    ) => {
      try {
        const outcome = await apiUpdateOutcome(outcomeId, {
          ...payload,
          mcp_url: settings.mcp_url,
        });
        pushToast("success", writeReceipt(outcome, "Outcome updated."));
        await refreshCanvas();
      } catch (error) {
        pushToast("error", `Could not update the outcome: ${(error as Error).message}`);
      }
    },
    [settings.mcp_url, pushToast, refreshCanvas],
  );

  const deleteOutcome = useCallback(
    async (outcomeId: string) => {
      try {
        const result = await apiDeleteOutcome(outcomeId, settings.mcp_url);
        pushToast("success", writeReceipt(result, "Outcome removed."));
        await refreshCanvas();
      } catch (error) {
        pushToast("error", `Could not remove the outcome: ${(error as Error).message}`);
      }
    },
    [settings.mcp_url, pushToast, refreshCanvas],
  );

  const deleteEvidence = useCallback(
    async (evidenceId: string) => {
      try {
        const result = await apiDeleteEvidence(evidenceId, settings.mcp_url);
        pushToast("success", writeReceipt(result, "Evidence removed."));
        await refreshCanvas();
      } catch (error) {
        pushToast("error", `Could not remove the evidence: ${(error as Error).message}`);
      }
    },
    [settings.mcp_url, pushToast, refreshCanvas],
  );

  const promoteEvidence = useCallback(
    async (
      evidenceId: string,
      payload: {
        target: "job" | "outcome";
        job_id?: string;
        statement?: string;
        name?: string;
        importance?: number;
        satisfaction?: number;
      },
    ) => {
      // The form keeps the error beside the quote it came from.
      const result = await apiPromoteEvidence(evidenceId, {
        ...payload,
        mcp_url: settings.mcp_url,
      });
      pushToast("success", writeReceipt(result, `Promoted the evidence to a ${payload.target}.`));
      await refreshCanvas();
    },
    [settings.mcp_url, pushToast, refreshCanvas],
  );
  const closePanel = useCallback(() => setActivePanel(null), []);

  const openPanel = useCallback(
    (panel: WorkspacePanelId) => {
      if (setupOpen) {
        closeSetup();
      }
      setActivePanel(panel);
    },
    [setupOpen, closeSetup],
  );

  /**
   * Point the studio at a subject and persist it, so a reload can resume on
   * the same job, step, or outcome. Evidence has no session slot.
   */
  const focusSubject = useCallback((kind: SignalSubjectKind, id: string) => {
    setFocusedSubject({ kind, id });
    if (kind === "evidence") {
      return;
    }
    saveSession(sessionForSubject(kind, id));
  }, []);

  /**
   * Stop speaking for the screen. The session slot goes with the selection, so a
   * reload cannot resurrect a focus the person just dismissed.
   */
  const clearFocus = useCallback(() => {
    setFocusedSubject(null);
    clearSession();
  }, []);

  /**
   * The one open-record path: focus the record and open the lens that shows it.
   * A signal card and a briefing line both land here.
   */
  const openRecord = useCallback(
    (kind: SignalSubjectKind, id: string) => {
      focusSubject(kind, id);
      const panel = PANEL_FOR_SUBJECT[kind];
      if (panel) {
        openPanel(panel);
      }
    },
    [focusSubject, openPanel],
  );

  /**
   * What a card does when activated: read the signal, then take the person to
   * the record it names. This is the job `targetId` never did.
   */
  const focusSignalSubject = useCallback(
    (signal: Signal) => {
      if (!signal.read_at) {
        markSignalAsRead(signal.id);
      }
      const kind = signal.subject_kind;
      const id = signal.subject_id;
      if (!kind || !id) {
        return;
      }
      openRecord(kind, id);
    },
    [markSignalAsRead, openRecord],
  );

  /**
   * A citation chip opens the record it names: the Evidence lens, focused on
   * that row. The snapshot label stays even when the record is gone.
   */
  const focusEvidence = useCallback(
    (evidenceId: string) => {
      setFocusedEvidenceId(evidenceId);
      openPanel("evidence");
    },
    [openPanel],
  );

  /**
   * Where the chip's promise came from: open the lens holding the record the
   * agent was told about, so the person can go read it instead of taking the
   * composer's word for it.
   */
  const revealFocusedSubject = useCallback(() => {
    if (!focusedSubject) {
      return;
    }
    if (focusedSubject.kind === "evidence") {
      focusEvidence(focusedSubject.id);
      return;
    }
    const panel = PANEL_FOR_SUBJECT[focusedSubject.kind];
    if (panel) {
      openPanel(panel);
    }
  }, [focusedSubject, focusEvidence, openPanel]);

  /**
   * What the snapshot calls the focused record, or null when it holds no such
   * record. The composer chip renders on this, never on the raw selection: an
   * indicator the canvas cannot name would claim a fact the store never said.
   */
  const focusedSubjectLabel = useMemo(
    () => focusLabel(canvasState.data, focusedSubject),
    [canvasState.data, focusedSubject],
  );

  /** The job owning the focused subject, so canvas panels can select it. */
  const focusedJobId = useMemo(() => {
    if (!focusedSubject) {
      return null;
    }
    const data = canvasState.data;
    if (!data) {
      return null;
    }
    const { kind, id } = focusedSubject;
    if (kind === "job") {
      return data.jobs.some((job) => job.id === id) ? id : null;
    }
    if (kind === "step") {
      return data.steps.find((step) => step.id === id)?.job_id ?? null;
    }
    if (kind === "outcome") {
      return data.outcomes.find((outcome) => outcome.id === id)?.job_id ?? null;
    }
    if (kind === "evidence") {
      return (data.evidence ?? []).find((item) => item.id === id)?.job_id ?? null;
    }
    return null;
  }, [focusedSubject, canvasState.data]);

  // The queue owns the follow-up sequence. The controller is created in a
  // mount effect — it reads refs at dispatch time, and doing that during
  // render is exactly what the React compiler forbids — and mirrored into
  // state so the runtime re-binds to its adapter once it exists. A stable
  // ref handle lets the dispatch-time callers reach it without a render race.
  const turnQueueRef = useRef<MessageQueueController | null>(null);
  const queueDispatch = useRef<(message: AppendMessage) => Promise<void>>(
    async () => undefined,
  );
  const [turnQueue, setTurnQueue] = useState<MessageQueueController | null>(null);
  useEffect(() => {
    const controller = createTurnQueue({
      run: (message) => queueDispatch.current(message),
      cancel: () => abortRef.current?.abort(),
    });
    turnQueueRef.current = controller;
    setTurnQueue(controller);
    return () => {
      turnQueueRef.current = null;
      controller.clear();
    };
  }, []);

  const stopStreaming = useCallback(() => {
    // Stop takes down the live turn (#410), not the lane: pausing the sequence
    // makes a queued follow-up wait for the next send instead of firing off
    // in the wake of the stop.
    turnQueueRef.current?.notifyCancelled();
    abortRef.current?.abort();
  }, []);

  /**
   * Re-read the history list: the switcher's rows, newest first.
   *
   * Declared before `runTurn` so a turn that creates or titles a thread can
   * refresh the list it is about to join.
   */
  const refreshConversations = useCallback(async () => {
    try {
      setConversations(await apiListConversations());
    } catch {
      /* history is a convenience; the current thread keeps working without it */
    }
  }, []);

  /**
   * One turn, from the user's words to the agent's last part.
   *
   * `base` is the visible path the turn answers, so the same machinery serves a
   * new message, a regeneration, and an edit without three copies of the stream
   * handling. The assistant-ui runtime owns the branch tree; this owns the
   * visible path and the wire.
   */
  const runTurn = useCallback(
    async (
      base: ChatMessage[],
      text: string,
      attachments: ChatAttachment[] = [],
      existingUserMessage?: ChatMessage,
    ) => {
      const trimmed = text.trim();
      // Starting a turn is separate from a turn being running (#410): the
      // queue serializes dispatches, so a settled stream never overlaps the
      // next one. Direct sends check `streaming` before calling this.
      if (!trimmed && attachments.length === 0) {
        return;
      }

      // Sending is the only evidence that matters here. streamChat asks the
      // sidecar first and the browser second, so the first message of a first run
      // is answered whether or not a local server exists. Refusing to try at all
      // because a background probe once said "down" is what made a working studio
      // look broken before the person had done anything.
      cancelScheduledProbes();
      // Writing here is the proof the new thread was wanted: Undo is spent.
      commitNewThread();

      // One clock for the turn: the question and the reply it opens carry the
      // same moment, which is what the transcript dates them by.
      const startedAt = new Date().toISOString();
      const userMessage: ChatMessage = existingUserMessage ?? {
        id: crypto.randomUUID(),
        parentId: base.length ? base[base.length - 1].id : null,
        role: "user",
        content: trimmed,
        createdAt: startedAt,
        ...(attachments.length ? { attachments } : {}),
      };
      const assistantId = crypto.randomUUID();
      const turnStartedAt = Date.now();
      let streamFrames = 0;
      const history: ChatMessage[] =
        existingUserMessage && base.at(-1)?.id === existingUserMessage.id
          ? base
          : [...base, userMessage];

      setMessages([
        ...history,
        {
          id: assistantId,
          parentId: userMessage.id,
          role: "assistant",
          content: "",
          parts: [],
          createdAt: startedAt,
        },
      ]);
      setStreaming(true);
      setThinkingPhase("health_check");
      setOfflineReplyFor(null);
      setToolActivity([]);

      const controller = new AbortController();
      liveTurnId.current = assistantId;
      abortRef.current = controller;

      let content = "";
      let parts: ChatPart[] = [];
      let failure: StudioError | null = null;
      let terminal = false;
      let stopped = false;
      let toolSeq = 0;

      // Prose is appended to the open text part; a surface opens a new one, so
      // the transcript keeps the agent's order instead of gathering all prose
      // above all cards.
      const appendText = (chunk: string) => {
        if (!chunk) {
          return;
        }
        content += chunk;
        const last = parts[parts.length - 1];
        parts =
          last?.kind === "text"
            ? [...parts.slice(0, -1), { kind: "text", text: last.text + chunk }]
            : [...parts, { kind: "text", text: chunk }];
      };

      const appendReasoning = (chunk: string) => {
        if (!chunk) {
          return;
        }
        const last = parts[parts.length - 1];
        parts =
          last?.kind === "reasoning"
            ? [...parts.slice(0, -1), { kind: "reasoning", text: last.text + chunk }]
            : [...parts, { kind: "reasoning", text: chunk }];
      };

      /** The open tool part for a name, if one is still waiting. */
      const openTool = (name: string) =>
        [...parts]
          .reverse()
          .find(
            (part): part is Extract<ChatPart, { kind: "tool" }> =>
              part.kind === "tool" && part.name === name && part.status === "running",
          );

      const applyToolEvent = (
        name: string,
        status: ToolStatus,
        preview?: string,
        id?: string,
      ) => {
        const open = openTool(name);
        if (status === "running") {
          if (open) {
            return;
          }
          toolSeq += 1;
          parts = [
            ...parts,
            { kind: "tool", id: id ?? `tool-${toolSeq}`, name, status },
          ];
          return;
        }
        if (open) {
          const next = {
            ...open,
            status,
            ...(preview ? { preview } : {}),
            // A result means the gate was answered; the question is spent.
            approval: undefined,
          };
          parts = [...parts.filter((part) => part !== open), next];
          return;
        }
        toolSeq += 1;
        parts = [
          ...parts,
          {
            kind: "tool",
            id: id ?? `tool-${toolSeq}`,
            name,
            status,
            ...(preview ? { preview } : {}),
          },
        ];
      };

      const publish = () => {
        setMessages((prev) =>
          prev.map((message) =>
            message.id === assistantId
              ? {
                  ...message,
                  content,
                  parts: [...parts],
                  ...(failure ? { error: failure, retryText: trimmed } : {}),
                }
              : message,
          ),
        );
      };

      const handleEvent = (event: RawSseEvent) => {
        streamFrames += 1;
        switch (event.event) {
          case "status": {
            const phase = String(event.data.phase ?? "");
            setThinkingPhase(phase);
            if (phase === "offline") {
              setOfflineReplyFor(assistantId);
            }
            break;
          }
          case "reasoning": {
            appendReasoning(String(event.data.text ?? ""));
            publish();
            break;
          }
          case "delta": {
            appendText(String(event.data.text ?? ""));
            publish();
            break;
          }
          case "source": {
            parts = [
              ...parts,
              {
                kind: "source",
                id: String(event.data.id ?? `src-${parts.length}`),
                title: String(event.data.title ?? ""),
                mediaType: String(event.data.mediaType ?? "application/json"),
                ...(event.data.filename ? { filename: String(event.data.filename) } : {}),
              },
            ];
            publish();
            break;
          }
          case "approval": {
            const approvalId = String(event.data.id ?? "");
            if (!approvalId) {
              break;
            }
            parts = [
              ...parts,
              {
                kind: "tool",
                id: String(event.data.tool_call_id ?? `approval-${approvalId}`),
                name: String(event.data.name ?? ""),
                status: "running",
                approval: {
                  id: approvalId,
                  prompt: String(event.data.prompt ?? "Allow this change?"),
                },
              },
            ];
            publish();
            break;
          }
          case "ui": {
            // Validate again on arrival: the connection is local but the
            // renderer must never trust a shape it has not checked.
            const parsed = parseUiSpec(event.data.spec, catalogManifest());
            if (parsed.ok) {
              parts = [
                ...parts,
                { kind: "ui", id: String(event.data.id ?? `ui-${parts.length}`), node: parsed.node },
              ];
              publish();
            }
            break;
          }
          case "tool": {
            const name = String(event.data.name ?? "");
            const status = String(event.data.status ?? "");
            const mapped: ToolStatus =
              status === "ok" || status === "error" || status === "declined" ? status : "running";
            applyToolEvent(
              name,
              mapped,
              event.data.preview ? String(event.data.preview) : undefined,
            );
            setToolActivity((prev) => [
              ...prev,
              { name, status, ...(event.data.preview ? { preview: String(event.data.preview) } : {}) },
            ]);
            publish();
            break;
          }
          case "message": {
            terminal = true;
            // The terminal frame is authoritative for the prose, but it must
            // never erase structured parts: thinking, tool calls, citations,
            // and surfaces sit between the paragraphs that frame them.
            content = String(event.data.content ?? content);
            const claims = readClaims(event.data.claims);
            if (claims.length > 0) {
              // The finished list replaces the streamed prose in place, so each
              // sentence keeps its own chip.
              let preceding = 0;
              for (const part of parts) {
                if (part.kind === "text") {
                  break;
                }
                preceding += 1;
              }
              const structured = parts.filter((part) => part.kind !== "text");
              parts = [
                ...structured.slice(0, preceding),
                { kind: "claims", content, claims },
                ...structured.slice(preceding),
              ];
            } else if (content && !parts.some((part) => part.kind === "text")) {
              parts = [...parts, { kind: "text", text: content }];
            }
            publish();
            break;
          }
          case "conversation": {
            const id = String(event.data.id ?? "");
            if (id) {
              setConversationId(id);
              // The thread was just created or titled: the history list would
              // otherwise show yesterday's answer until a reload.
              void refreshConversations();
            }
            break;
          }
          case "memory": {
            const observation = event.data.observation as Observation | undefined;
            if (observation?.id) {
              setMemory((prev) =>
                prev.some((item) => item.id === observation.id)
                  ? prev.map((item) => (item.id === observation.id ? observation : item))
                  : [...prev, observation],
              );
            }
            break;
          }
          case "canvas_dirty":
            void refreshCanvas();
            break;
          case "connector": {
            if (String(event.data.status ?? "") === "error") {
              const reason = String(event.data.error ?? "The connector could not be added.");
              setMessages((prev) => [
                ...prev,
                {
                  id: crypto.randomUUID(),
                  parentId: assistantId,
                  role: "notice",
                  content: `Connector failed: ${reason}`,
                },
              ]);
            } else {
              setConnectorSuggestions((prev) => {
                const id = String(event.data?.preset ?? event.data?.name ?? "");
                if (!id || prev.includes(id)) {
                  return prev;
                }
                return [...prev, id];
              });
            }
            void refreshConnectors();
            break;
          }
          case "error": {
            terminal = true;
            failure = readStudioError(event.data.error);
            publish();
            break;
          }
          default:
            break;
        }
      };

      try {
        await streamChat(
          {
            base_url: settings.base_url,
            api_key: settings.api_key,
            model: settings.model_name,
            mcp_url: settings.mcp_url,
            messages: history,
            brief,
            ui_catalog: catalogManifest(),
            conversation_id: conversationId,
            attachments,
            approvals: true,
            assistant_id: assistantId,
            focus: focusPointer(focusedSubject),
          },
          handleEvent,
          controller.signal,
        );
      } catch (error) {
        const aborted = (error as Error).name === "AbortError";
        if (aborted) {
          // An abort is the user's own doing: drop the empty placeholder, keep
          // the question, and report no failure — the assistant did not break.
          stopped = true;
          setMessages((prev) =>
            prev.filter((message) => message.id !== assistantId || message.content !== ""),
          );
        } else {
          terminal = true;
          failure = asStudioError(error);
          recordStudioError(failure, "/api/chat");
          publish();
        }
      } finally {
        if (!terminal && !failure && !stopped) {
          // The stream ended without a message or an error: something failed
          // silently, and the user must still be told.
          failure = {
            code: "internal",
            message: "The assistant stopped before answering.",
            suggestion: "Try again — your question is still here.",
            retryable: true,
          };
          recordStudioError(failure, "/api/chat");
          publish();
        }
        recordStream({
          assistant_id: assistantId,
          frames: streamFrames,
          terminal: failure ? "failed" : stopped ? "stopped" : "completed",
          duration_ms: Math.max(0, Date.now() - turnStartedAt),
        });
        if (liveTurnId.current === assistantId) {
          // Only the newest turn on the wire may clear the running state: a
          // steered cut-in is already live while this one settles (#410).
          liveTurnId.current = null;
          setStreaming(false);
          setThinkingPhase(null);
          abortRef.current = null;
        }
      }
    },
    [
      settings,
      brief,
      conversationId,
      focusedSubject,
      refreshCanvas,
      refreshConnectors,
      refreshConversations,
      cancelScheduledProbes,
      commitNewThread,
    ],
  );

  // The newest transcript and turn machinery, handed to the queue after every
  // commit. No send can happen before the first commit's effects have run.
  useEffect(() => {
    queueDispatch.current = async (message) => {
      const custom = message.metadata?.custom as
        | { quote?: ComposerQuote; attachments?: ChatAttachment[] }
        | undefined;
      await runTurn(
        messages,
        textWithQuote(textOf(message), custom?.quote),
        // A composer send carries file ids the attachment adapter can re-read; a
        // studio send carries the prepared extraction itself (see #410's queue).
        custom?.attachments ?? preparedAttachments(message.attachments),
      );
    };
  });

  const sendMessage = useCallback(
    async (text: string, attachments: ChatAttachment[] = []) => {
      const trimmed = text.trim();
      if (!trimmed && attachments.length === 0) {
        return;
      }
      // Every send enters through the queue (#410): idle, the controller
      // dispatches it synchronously — the old direct path; mid-run, it joins
      // the lane. A ref-read of "is a turn open" would race two same-tick
      // sends; the controller's busy edge is the one that cannot. The promise
      // settles when the send is accepted into the sequence, not when its
      // turn answers.
      turnQueue?.adapter.enqueue(
        queuedUserMessage(
          trimmed,
          messages.length ? messages[messages.length - 1].id : null,
          attachments,
        ),
      );
    },
    [messages, turnQueue],
  );

  /**
   * The turn after `messageId` is regenerated as a sibling, so the previous
   * answer is still there behind the branch picker.
   */
  const regenerateFrom = useCallback(
    async (messageId: string | null) => {
      if (streaming) {
        return;
      }
      const index = messageId
        ? messages.findIndex((message) => message.id === messageId)
        : messages.length - 1;
      if (index < 0) {
        return;
      }
      const target = messages[index];
      const questionIndex =
        target?.role === "user"
          ? index
          : target?.role === "assistant"
            ? index - 1
            : -1;
      const question = messages[questionIndex];
      if (!question || question.role !== "user") {
        return;
      }
      await runTurn(
        messages.slice(0, questionIndex + 1),
        question.content,
        question.attachments ?? [],
        question,
      );
    },
    [messages, runTurn, streaming],
  );

  const editFrom = useCallback(
    async (messageId: string | null, text: string, attachments: ChatAttachment[] = []) => {
      if (streaming) {
        return;
      }
      const index = messageId
        ? messages.findIndex((message) => message.id === messageId)
        : messages.length - 1;
      const original = messages[index];
      if (index < 0 || original?.role !== "user") {
        return;
      }
      const edited: ChatMessage = {
        ...original,
        id: crypto.randomUUID(),
        content: text.trim(),
        ...(attachments.length ? { attachments } : { attachments: undefined }),
      };
      await runTurn(messages.slice(0, index), edited.content, attachments, edited);
    },
    [messages, runTurn, streaming],
  );

  const switchBranch = useCallback(
    (next: ChatMessage[]) => {
      setMessages(next);
      const head = next.length ? next[next.length - 1].id : null;
      if (conversationId) {
        // The branch a person chose is the one that opens next time.
        void apiSetConversationHead(conversationId, head).catch(() => undefined);
      }
    },
    [conversationId],
  );

  const respondToApproval = useCallback(
    async (approvalId: string, approved: boolean, reason = "") => {
      try {
        await apiResolveApproval(approvalId, approved, reason);
      } catch {
        pushToast("error", "That approval request is no longer waiting.");
      }
      // The paused stream carries the outcome; the local question is spent
      // either way, and a stale prompt must not invite a second click.
      setMessages((prev) =>
        prev.map((message) => ({
          ...message,
          ...(message.parts
            ? {
                parts: message.parts.map((part) =>
                  part.kind === "tool" && part.approval?.id === approvalId
                    ? { ...part, approval: undefined }
                    : part,
                ),
              }
            : {}),
        })),
      );
    },
    [pushToast],
  );


  /** The single conversational exit from any lens. */
  const ask = useCallback(
    (intent: string) => {
      setActivePanel(null);
      void sendMessage(intent);
    },
    [sendMessage],
  );

  const refreshMemory = useCallback(async () => {
    setMemoryLoading(true);
    try {
      setMemory(await fetchMemory());
    } catch {
      /* memory is a convenience; the studio keeps working without it */
    } finally {
      setMemoryLoading(false);
    }
  }, []);

  const addObservation = useCallback(
    async (payload: AddObservationPayload) => {
      try {
        const observation = await apiAddObservation(payload);
        setMemory((prev) => [...prev, observation]);
        return observation;
      } catch {
        pushToast("error", "I couldn't save that context.");
        return null;
      }
    },
    [pushToast],
  );

  const updateObservation = useCallback(
    async (observationId: string, payload: UpdateObservationPayload) => {
      try {
        const observation = await apiUpdateObservation(observationId, payload);
        setMemory((prev) =>
          observation.status === "dismissed"
            ? prev.filter((item) => item.id !== observationId)
            : prev.map((item) => (item.id === observationId ? observation : item)),
        );
        return observation;
      } catch {
        pushToast("error", "I couldn't update that context.");
        return null;
      }
    },
    [pushToast],
  );

  const deleteObservation = useCallback(
    async (observationId: string) => {
      try {
        await apiDeleteObservation(observationId);
        setMemory((prev) => prev.filter((item) => item.id !== observationId));
      } catch (error) {
        const problem = asStudioError(error);
        recordStudioError(problem, "/api/memory/observations");
        pushToast("error", "I couldn't forget that.");
      }
    },
    [pushToast],
  );

  const clearMemory = useCallback(async () => {
    try {
      await apiClearMemory();
      setMemory([]);
      setConversationId(null);
      setMessages([]);
      setToolActivity([]);
    } catch (error) {
      const problem = asStudioError(error);
      recordStudioError(problem, "/api/memory");
      pushToast("error", "I couldn't clear what I've learned.");
    }
  }, [pushToast]);

  const openConversation = useCallback(
    async (targetId: string) => {
      abortRef.current?.abort();
      abortRef.current = null;
      setStreaming(false);
      setThinkingPhase(null);
      setOfflineReplyFor(null);
      setToolActivity([]);
      // The tree, not the flat turn list: a thread with branches must open on
      // the branch that was visible when it was left. A conversation is never
      // opened without its turns.
      const tree = await fetchConversationTree(targetId);
      setConversationId(targetId);
      setMessages(turnsToMessages(tree.messages, tree.head_id));
      void refreshConversations();
    },
    [refreshConversations],
  );

  const clearChat = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    // A fresh chat is also a fresh lane: follow-ups typed for the old
    // conversation must not fire into the new one.
    turnQueueRef.current?.clear();
    setMessages([]);
    setToolActivity([]);
    setStreaming(false);
    setThinkingPhase(null);
    setOfflineReplyFor(null);
    setConversationId(null);
    void apiCreateConversation()
      .then((conversation) =>
        setConversationId((current) => current ?? conversation.id),
      )
      .catch(() => undefined);
  }, []);

  // First paint shows the person's own work; nothing that nobody asked for gets
  // to declare the studio broken. Boot order, and why nothing on the first
  // screen waits on the network:
  //   1. Local data first — the canvas, memory, and the latest conversation read
  //      from IndexedDB and paint the person's own work one tick after mount.
  //   2. Config alongside it, never a gate. `fetchConfig` bounds itself, so a
  //      request that hangs cannot hold anything behind it; boot carries on with
  //      the defaults it already has.
  //   3. Everything else last — connectors, presets, featured, and the capability
  //      probes (which ride along with the health survey) belong to Settings and
  //      the tour, not the stage, so they wait for idle.
  useEffect(() => {
    let cancelled = false;

    // (1) The board and the thread are local data: they read from IndexedDB and never
    // wait on a server that may not exist. They land one tick after mount, so the
    // first thing painted is the shell and not a render inside a render.
    const loadLocalData = async () => {
      await Promise.resolve();
      void refreshCanvas();
      void refreshMemory();
      void refreshConversations();
      const { conversation } = await fetchLatestConversation();
      if (cancelled || !conversation) {
        return;
      }
      setConversationId(conversation.id);
      // The tree, not the flat turn list: a conversation with branches
      // must open on the branch that was visible when it was left.
      const tree = await fetchConversationTree(conversation.id);
      if (cancelled) {
        return;
      }
      setMessages(turnsToMessages(tree.messages, tree.head_id));
    };
    void loadLocalData().catch(() => undefined);

    // Configuration is a convenience, not a gate. It may fill defaults for a
    // browser that has none; a failure is silent, because a hosted studio with no
    // sidecar configured answers 502 by design and that is not an outage. A
    // damaged database is the one exception: the sidecar is up and telling us the
    // only copy is damaged, so the failure page replaces the shell rather than
    // letting the board look merely empty.
    fetchConfig()
      .then((defaults) => {
        if (cancelled) {
          return;
        }
        setSidecarReachable(true);
        setBootError(null);
        if (localStorage.getItem(SETTINGS_KEY) === null) {
          saveSettings(defaults);
        }
      })
      .catch((error) => {
        if (cancelled) {
          return;
        }
        const problem = asStudioError(error);
        if (problem.code === "store_corrupt") {
          setBootError(problem);
          setSidecarReachable(true);
        }
      });

    // Status rows, capabilities, and the connector list are read in Settings and
    // in the tour, not on the stage. Let the first screen settle; give the probes
    // up entirely if the person starts talking before the browser is idle.
    const probe = () => {
      idleProbeRef.current = null;
      if (cancelled) {
        return;
      }
      void checkConnections({}, "recovery");
      void refreshConnectors();
      void refreshPresets();
      void refreshFeatured();
    };
    if (typeof window.requestIdleCallback === "function") {
      const handle = window.requestIdleCallback(probe, { timeout: PROBE_IDLE_TIMEOUT_MS });
      idleProbeRef.current = { cancel: () => window.cancelIdleCallback(handle) };
    } else {
      const timer = window.setTimeout(probe, PROBE_IDLE_TIMEOUT_MS);
      idleProbeRef.current = { cancel: () => window.clearTimeout(timer) };
    }

    return () => {
      cancelled = true;
      const handle = idleProbeRef.current;
      idleProbeRef.current = null;
      handle?.cancel();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Probing on a schedule that respects the person (#535). One scheduler owns
  // the timer: 30 s while the tab is visible, doubling to a five-minute cap on
  // consecutive failures, and nothing at all while the tab is hidden. On return
  // it probes once, but only if the last answer has gone stale. This may retire
  // a warning, never raise one.
  useEffect(() => {
    const scheduler = createProbeScheduler({
      probe: () => probeNowRef.current(),
    });
    probeSchedulerRef.current = scheduler;
    scheduler.start();
    return () => {
      scheduler.stop();
      probeSchedulerRef.current = null;
    };
  }, []);

  // While the breaker is open the countdown is the only thing changing, so tick
  // it once a second — the timer that carries it is separate from the probe
  // schedule, and it stops the moment the breaker closes or is reset (#536).
  useEffect(() => {
    if (probeRetry.state !== "open") {
      return;
    }
    const timer = window.setInterval(publishProbeRetry, 1_000);
    return () => window.clearInterval(timer);
  }, [probeRetry.state, publishProbeRetry]);

  // A network that comes back is worth one probe; a network that goes away is
  // worth one sentence and no further requests until it returns. The scheduler
  // itself keeps running, so the timer resumes with the connection.
  useEffect(() => {
    const onOnline = () => {
      probeSchedulerRef.current?.check();
    };
    const onOffline = () => {
      applyOffline();
    };
    window.addEventListener("online", onOnline);
    window.addEventListener("offline", onOffline);
    return () => {
      window.removeEventListener("online", onOnline);
      window.removeEventListener("offline", onOffline);
    };
  }, [applyOffline]);

  // A settings edit that changes what the studio talks to is a person changing
  // the endpoint, so it earns one probe — debounced, because typing a URL is
  // many changes in a row, and restarting the cadence, because the endpoint
  // that failed is not the one they just entered. The debounce timer lives on
  // the ref and is scheduled by `saveSettings`, so a re-render that only swaps
  // the probe's identity cannot cancel the probe it just promised.
  useEffect(() => {
    settingsProbeRef.current = () => {
      if (!isOnline()) {
        applyOffline();
        return;
      }
      void surveyConnections({})
        .then((report) => applyReport(report, "evidence"))
        .then(() => probeSchedulerRef.current?.reset())
        .catch(() => undefined);
    };
  }, [surveyConnections, applyReport, applyOffline]);

  // Hand the pending settings probe back on unmount, and only on unmount.
  useEffect(
    () => () => {
      if (settingsProbeTimerRef.current !== null) {
        clearTimeout(settingsProbeTimerRef.current);
        settingsProbeTimerRef.current = null;
      }
    },
    [],
  );

  // The inbox is server state, so it is re-read rather than remembered: every
  // minute the window is up, and the moment it comes back into focus.
  useEffect(() => {
    const poll = () => {
      if (document.visibilityState === "visible") {
        void refreshSignals();
      }
    };

    const timer = window.setInterval(poll, SIGNAL_POLL_INTERVAL_MS);
    document.addEventListener("visibilitychange", poll);

    return () => {
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", poll);
    };
  }, [refreshSignals]);

  // The canvas is one state, not four booleans: an empty board and a failed
  // board must never look the same.
  const canvas = canvasState.data;
  const canvasLoading = canvasState.kind === "loading";
  const canvasError = canvasState.kind === "error" ? canvasState.error : null;

  // Re-probe after the person restored a backup: a clean answer clears the boot
  // page and re-hydrates the studio in place.
  const recheckBoot = useCallback(async () => {
    try {
      const defaults = await fetchConfig();
      setSidecarReachable(true);
      setBootError(null);
      if (localStorage.getItem(SETTINGS_KEY) === null) {
        saveSettings(defaults);
      }
    } catch (error) {
      const problem = asStudioError(error);
      if (problem.code === "store_corrupt") {
        setBootError(problem);
        setSidecarReachable(true);
        return;
      }
      setSidecarReachable(false);
      return;
    }
    void refreshCapabilities();
    void refreshCanvas();
    void refreshConnectors();
    void refreshPresets();
    void refreshFeatured();
    void refreshMemory();
  }, [
    saveSettings,
    refreshCapabilities,
    refreshCanvas,
    refreshConnectors,
    refreshPresets,
    refreshFeatured,
    refreshMemory,
  ]);

  const deviceStatus = useMemo(
    () => deriveDeviceStatus(capabilities, capabilitiesCheckedAt),
    [capabilities, capabilitiesCheckedAt],
  );

  const value = useMemo<StudioContextValue>(
    () => ({
      settings,
      saveSettings,
      displayName,
      setDisplayName,
      brief,
      saveBrief,
      setupOpen,
      openSetup,
      closeSetup,
      canvas,
      canvasLoading,
      canvasCached,
      canvasState,
      canvasError,
      refreshCanvas,
      llmHealth,
      probeRetry,
      models,
      modelsLoading,
      modelsMessage,
      refreshModels,
      mcpReachable,
      sidecarReachable,
      bootError,
      recheckBoot,
      dismissedSidecarNotice,
      dismissSidecarNotice,
      recheckConnections,
      checkConnections,
      surveyConnections,
      messages,
      streaming,
      thinkingPhase,
      toolActivity,
      sendMessage,
      regenerateFrom,
      editFrom,
      switchBranch,
      respondToApproval,
      stopStreaming,
      queue: turnQueue?.adapter ?? null,
      clearChat,
      startNewThread,
      conversationId,
      conversations,
      refreshConversations,
      openConversation,
      memory,
      memoryLoading,
      refreshMemory,
      addObservation,
      updateObservation,
      deleteObservation,
      clearMemory,
      pushNotice,
      offlineReplyFor,
      addStep,
      addOutcome,
      promoteEvidence,
      createJob,
      updateJob,
      deleteJob,
      updateStep,
      deleteStep,
      updateOutcome,
      deleteOutcome,
      deleteEvidence,
      activePanel,
      openPanel,
      closePanel,
      ask,
      pushToast,
      dismissToast,
      connectors,
      connectorsError,
      connectorsLoading,
      capabilities,
      deviceStatus,
      presets,
      presetError,
      presetsLoading,
      refreshConnectors,
      refreshPresets,
      refreshCapabilities,
      addConnector,
      deleteConnector,
      connectorSuggestions,
      dismissConnectorSuggestion,
      customizeOpen,
      customizeTarget,
      openCustomize,
      closeCustomize,
      marketplace,
      marketplaceError,
      marketplaceLoading,
      searchMarketplace,
      featured,
      featuredError,
      refreshFeatured,
      installFromMarketplace,
      connectorSuggestion,
      dismissConnectorModal,
      theses,
      saveThesis,
      deleteThesis,
      signals,
      unreadSignalCount,
      signalsError,
      refreshSignals,
      markSignalAsRead,
      dismissSignal,
      focusSignalSubject,
      focusSubject,
      openRecord,
      clearFocus,
      focusedSubject,
      focusedSubjectLabel,
      revealFocusedSubject,
      focusedJobId,
      segments,
      strategy,
      segmentsError,
      refreshSegments,
      focusedEvidenceId,
      focusEvidence,
    }),
    [
      settings,
      saveSettings,
      displayName,
      setDisplayName,
      brief,
      saveBrief,
      setupOpen,
      openSetup,
      closeSetup,
      canvas,
      canvasLoading,
      canvasCached,
      canvasState,
      canvasError,
      refreshCanvas,
      llmHealth,
      probeRetry,
      models,
      modelsLoading,
      modelsMessage,
      refreshModels,
      mcpReachable,
      sidecarReachable,
      bootError,
      recheckBoot,
      dismissedSidecarNotice,
      dismissSidecarNotice,
      recheckConnections,
      checkConnections,
      surveyConnections,
      messages,
      streaming,
      thinkingPhase,
      toolActivity,
      sendMessage,
      regenerateFrom,
      editFrom,
      switchBranch,
      respondToApproval,
      stopStreaming,
      turnQueue,
      clearChat,
      startNewThread,
      conversationId,
      conversations,
      refreshConversations,
      openConversation,
      memory,
      memoryLoading,
      refreshMemory,
      addObservation,
      updateObservation,
      deleteObservation,
      clearMemory,
      pushNotice,
      offlineReplyFor,
      addStep,
      addOutcome,
      promoteEvidence,
      createJob,
      updateJob,
      deleteJob,
      updateStep,
      deleteStep,
      updateOutcome,
      deleteOutcome,
      deleteEvidence,
      activePanel,
      openPanel,
      closePanel,
      ask,
      pushToast,
      dismissToast,
      connectors,
      connectorsError,
      connectorsLoading,
      capabilities,
      deviceStatus,
      presets,
      presetError,
      presetsLoading,
      refreshConnectors,
      refreshPresets,
      refreshCapabilities,
      addConnector,
      deleteConnector,
      connectorSuggestions,
      dismissConnectorSuggestion,
      customizeOpen,
      customizeTarget,
      openCustomize,
      closeCustomize,
      marketplace,
      marketplaceError,
      marketplaceLoading,
      searchMarketplace,
      featured,
      featuredError,
      refreshFeatured,
      installFromMarketplace,
      connectorSuggestion,
      dismissConnectorModal,
      theses,
      saveThesis,
      deleteThesis,
      signals,
      unreadSignalCount,
      signalsError,
      refreshSignals,
      markSignalAsRead,
      dismissSignal,
      focusSignalSubject,
      focusSubject,
      clearFocus,
      openRecord,
      focusedSubject,
      focusedSubjectLabel,
      revealFocusedSubject,
      focusedJobId,
      segments,
      strategy,
      segmentsError,
      refreshSegments,
      focusedEvidenceId,
      focusEvidence,
    ],
  );

  return <StudioContext.Provider value={value}>{children}</StudioContext.Provider>;
}

export function StudioProvider({ children }: { children: ReactNode }) {
  return (
    <SettingsProvider>
      <NoticesProvider>
        <StudioProviderInner>{children}</StudioProviderInner>
      </NoticesProvider>
    </SettingsProvider>
  );
}

export function useStudio(): StudioContextValue {
  const context = useContext(StudioContext);
  if (!context) {
    throw new Error("useStudio must be used within a StudioProvider");
  }
  return context;
}
