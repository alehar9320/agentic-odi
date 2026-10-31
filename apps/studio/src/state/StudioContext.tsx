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
  fetchSignals,
  fetchUnreadSignalCount,
  healthLlm,
  healthMcp,
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
import { capabilityRegistry, type Capability } from "../bff/capabilities/registry";
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
  CustomizeTarget,
  MarketplaceListing,
  MarketplaceSearch,
  Observation,
  Signal,
  SignalSubjectKind,
  StudioBrief,
  StudioConfig,
  StudioError,
  StudioTheme,
  Thesis,
  ToolStatus,
  TurnNode,
  WorkspacePanelId,
} from "../types";
import { catalogManifest } from "../ui/catalog";
import { parseUiSpec } from "../ui/protocol";
import { recordStream, recordStudioError } from "../diagnostics/bundle";

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

const SETTINGS_KEY = "studio.settings";
const CANVAS_KEY = "studio.canvas";
const DISPLAY_NAME_KEY = "studio.displayName";
const BRIEF_KEY = "studio.brief";
const SIDECAR_NOTICE_DISMISSED_KEY = "studio.sidecarNoticeDismissed";
const THESES_KEY = "studio.theses";

/** How often the studio re-probes the model and the MCP server. */
const HEALTH_POLL_INTERVAL_MS = 30_000;

/** How often a focused window re-reads the signal inbox from the store. */
const SIGNAL_POLL_INTERVAL_MS = 60_000;

/** The lens that can show a signal's subject. Unwired kinds navigate nowhere. */
const PANEL_FOR_SUBJECT: Partial<Record<SignalSubjectKind, WorkspacePanelId>> = {
  job: "jobmap",
  step: "jobmap",
  outcome: "landscape",
  evidence: "evidence",
};

export const EMPTY_CONFIG: StudioConfig = {
  base_url: "http://localhost:8001/v1",
  api_key: "local",
  model_name: "local-tools-model",
  mcp_url: "http://localhost:8000/mcp",
  theme: "dark",
};

export type ToastKind = "success" | "error" | "info";

export interface Toast {
  id: number;
  kind: ToastKind;
  message: string;
}

export interface ToolActivity {
  name: string;
  status: string;
  preview?: string;
}

export interface ConnectionReport {
  sidecarReachable: boolean;
  mcpReachable: boolean;
  llmHealthy: boolean;
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
  /** Model ids the configured endpoint publishes. Empty means "type one". */
  models: string[];
  modelsLoading: boolean;
  /** Why the endpoint would not list models, if it would not. */
  modelsMessage: string | null;
  refreshModels: (config?: { base_url: string; api_key: string }) => Promise<void>;
  mcpReachable: boolean;
  sidecarReachable: boolean | null;
  /** Whether the user has dismissed this session's sidecar-down notice. */
  dismissedSidecarNotice: boolean;
  /** Probe again now, e.g. after the user started the sidecar. */
  recheckConnections: () => Promise<void>;
  dismissSidecarNotice: () => void;
  /** Probe the sidecar, MCP server, and model. Optionally against unsaved config. */
  checkConnections: (override?: Partial<StudioConfig>) => Promise<ConnectionReport>;
  messages: ChatMessage[];
  streaming: boolean;
  thinkingPhase: string | null;
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
  clearChat: () => void;
  conversationId: string | null;
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
  offlineReply: boolean;
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
  toasts: Toast[];
  pushToast: (kind: ToastKind, message: string) => void;
  dismissToast: (id: number) => void;
  connectors: ConnectorListItem[];
  presets: ConnectorPreset[];
  /** The failure behind an unreachable connector catalog, if any. */
  presetError: StudioError | null;
  /** The failure behind an unreachable connector list, if any. */
  connectorsError: StudioError | null;
  /** Probed availability of local and sidecar capabilities. */
  capabilities: Capability[];
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
  focusedSubject: { kind: SignalSubjectKind; id: string } | null;
  /** The job that owns the focused subject, so canvas panels can select it. */
  focusedJobId: string | null;
  /** The evidence record a citation chip asked the Evidence lens to show. */
  focusedEvidenceId: string | null;
  focusEvidence: (evidenceId: string) => void;
}

const StudioContext = createContext<StudioContextValue | null>(null);

function loadSettings(): StudioConfig {
  try {
    const raw = localStorage.getItem(SETTINGS_KEY);
    if (raw) {
      return { ...EMPTY_CONFIG, ...(JSON.parse(raw) as Partial<StudioConfig>) };
    }
  } catch {
    /* ignore malformed cache */
  }
  return EMPTY_CONFIG;
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

function loadSidecarNoticeDismissed(): boolean {
  try {
    return localStorage.getItem(SIDECAR_NOTICE_DISMISSED_KEY) === "1";
  } catch {
    return false;
  }
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
      job_id: parsed.job_id ? String(parsed.job_id) : undefined,
    };
    return brief.product_name || brief.job_statement ? brief : null;
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

export function StudioProvider({ children }: { children: ReactNode }) {
  const [settings, setSettings] = useState<StudioConfig>(loadSettings);
  const theme: StudioTheme = settings.theme === "light" ? "light" : "dark";
  const [displayName, setDisplayNameState] = useState<string>(loadDisplayName);
  const [brief, setBrief] = useState<StudioBrief | null>(loadBrief);
  // The context conversation is never a gate. It opens from the stage, from a
  // hint once the studio has answered something, from /start, or from Settings.
  const [setupOpen, setSetupOpen] = useState(false);
  const [offlineReply, setOfflineReply] = useState(false);
  const [canvasState, setCanvasState] = useState<CanvasState>(() => {
    const cached = loadCanvasCache();
    return cached ? { kind: "loading", data: cached } : { kind: "loading", data: null };
  });
  const [canvasCached, setCanvasCached] = useState(() => loadCanvasCache() !== null);
  const [llmHealth, setLlmHealth] = useState<{ healthy: boolean | null; message: string }>({
    healthy: null,
    message: "Health not checked yet.",
  });
  const [models, setModels] = useState<string[]>([]);
  const [modelsLoading, setModelsLoading] = useState(false);
  const [modelsMessage, setModelsMessage] = useState<string | null>(null);
  const [mcpReachable, setMcpReachable] = useState(false);
  const [sidecarReachable, setSidecarReachable] = useState<boolean | null>(null);
  const [dismissedSidecarNotice, setDismissedSidecarNotice] = useState<boolean>(loadSidecarNoticeDismissed);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [memory, setMemory] = useState<Observation[]>([]);
  const [memoryLoading, setMemoryLoading] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [thinkingPhase, setThinkingPhase] = useState<string | null>(null);
  const [toolActivity, setToolActivity] = useState<ToolActivity[]>([]);
  const [activePanel, setActivePanel] = useState<WorkspacePanelId | null>(null);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [connectors, setConnectors] = useState<ConnectorListItem[]>([]);
  const [presets, setPresets] = useState<ConnectorPreset[]>([]);
  const [presetError, setPresetError] = useState<StudioError | null>(null);
  const [connectorsError, setConnectorsError] = useState<StudioError | null>(null);
  const [capabilities, setCapabilities] = useState<Capability[]>([]);
  const [connectorSuggestions, setConnectorSuggestions] = useState<string[]>([]);
  const [serverSignals, setServerSignals] = useState<Signal[]>([]);
  const [unreadSignalCount, setUnreadSignalCount] = useState(0);
  const [signalsError, setSignalsError] = useState<StudioError | null>(null);
  const [focusedSubject, setFocusedSubject] = useState<{
    kind: SignalSubjectKind;
    id: string;
  } | null>(null);
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
  const toastId = useRef(0);
  const abortRef = useRef<AbortController | null>(null);

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


  const pushToast = useCallback((kind: ToastKind, message: string) => {
    const id = (toastId.current += 1);
    setToasts((prev) => [...prev, { id, kind, message }]);
    window.setTimeout(() => {
      setToasts((prev) => prev.filter((toast) => toast.id !== id));
    }, 6000);
  }, []);

  const dismissToast = useCallback((id: number) => {
    setToasts((prev) => prev.filter((toast) => toast.id !== id));
  }, []);

  const dismissConnectorSuggestion = useCallback((preset: string) => {
    setConnectorSuggestions((prev) => prev.filter((s) => s !== preset));
  }, []);

  const refreshConnectors = useCallback(async () => {
    setConnectorsError(null);
    try {
      setConnectors(await fetchConnectors());
    } catch (error) {
      // A list that could not be fetched is not an empty list.
      setConnectorsError(asStudioError(error));
      setConnectors([]);
    }
  }, []);

  const refreshPresets = useCallback(async () => {
    setPresetError(null);
    try {
      setPresets(await fetchConnectorCatalog());
    } catch (error) {
      // An unreachable catalog is a failure, not an empty catalog: the settings
      // panel says so instead of offering a select with nothing in it.
      setPresetError(asStudioError(error));
      setPresets([]);
    }
  }, []);

  const refreshCapabilities = useCallback(async () => {
    try {
      setCapabilities(await capabilityRegistry.statuses(settings));
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

  // The theme lives on <html> so every surface, portal, and native control
  // follows one class instead of each component tracking its own copy.
  useEffect(() => {
    const root = document.documentElement;
    root.classList.toggle("theme-light", theme === "light");
    root.classList.toggle("theme-dark", theme === "dark");
    root.style.colorScheme = theme;
  }, [theme]);

  const saveSettings = useCallback((config: StudioConfig) => {
    setSettings(config);
    try {
      localStorage.setItem(SETTINGS_KEY, JSON.stringify(config));
    } catch {
      /* storage unavailable */
    }
  }, []);

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

  const checkConnections = useCallback(
    async (override: Partial<StudioConfig> = {}): Promise<ConnectionReport> => {
      const target = { ...settings, ...override };
      const [sidecar, mcp, llm] = await Promise.all([
        fetchConfig()
          .then(() => true)
          .catch(() => false),
        healthMcp(target.mcp_url)
          .then((result) => result.reachable)
          .catch(() => false),
        healthLlm({
          base_url: target.base_url,
          api_key: target.api_key,
          model: target.model_name,
        }).catch((error: unknown) => ({
          healthy: false,
          message: (error as Error).message || "The model did not answer.",
        })),
      ]);

      setSidecarReachable(sidecar);
      setMcpReachable(mcp);
      setLlmHealth(llm);
      void refreshCapabilities();
      if (sidecar) {
        setDismissedSidecarNotice(false);
      }
      return { sidecarReachable: sidecar, mcpReachable: mcp, llmHealthy: llm.healthy };
    },
    [settings, refreshCapabilities],
  );

  // Re-probe after the user acted on the sidecar notice (e.g. started the
  // sidecar). Resolves once the report is in so the UI can stop showing "busy".
  const recheckConnections = useCallback(async () => {
    await checkConnections();
  }, [checkConnections]);

  const dismissSidecarNotice = useCallback(() => {
    setDismissedSidecarNotice(true);
    try {
      localStorage.setItem(SIDECAR_NOTICE_DISMISSED_KEY, "1");
    } catch {
      /* storage unavailable */
    }
  }, []);

  const refreshCanvas = useCallback(async () => {
    // The inbox is re-read alongside the board: every path that reaches this
    // function either just changed the store or is checking what changed, and
    // a canvas that fails to load must not leave the bell showing stale counts.
    void refreshSignals();
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
  }, [settings.mcp_url, refreshSignals]);

  const addStep = useCallback(
    async (payload: Omit<AddStepPayload, "mcp_url">) => {
      try {
        await apiAddStep({ ...payload, mcp_url: settings.mcp_url });
        pushToast("success", "Step added to Job Map!");
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
      // it, so the error travels up instead of disappearing into a toast.
      await apiAddOutcome({ ...payload, mcp_url: settings.mcp_url });
      pushToast("success", "Outcome captured successfully!");
      await refreshCanvas();
    },
    [settings.mcp_url, pushToast, refreshCanvas],
  );

  const createJob = useCallback(
    async (payload: { name: string; description?: string }): Promise<string | null> => {
      const job = await apiCreateJob({ ...payload, mcp_url: settings.mcp_url });
      pushToast("success", `Job created: ${payload.name}`);
      await refreshCanvas();
      return job.id ?? null;
    },
    [settings.mcp_url, pushToast, refreshCanvas],
  );

  const updateJob = useCallback(
    async (jobId: string, payload: { name?: string; description?: string }) => {
      try {
        await apiUpdateJob(jobId, { ...payload, mcp_url: settings.mcp_url });
        pushToast("success", "Job updated.");
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
        await apiDeleteJob(jobId, settings.mcp_url);
        pushToast("success", "Job removed.");
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
        await apiUpdateStep(stepId, { ...payload, mcp_url: settings.mcp_url });
        pushToast("success", "Step updated.");
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
        await apiDeleteStep(stepId, settings.mcp_url);
        pushToast("success", "Step removed.");
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
        await apiUpdateOutcome(outcomeId, { ...payload, mcp_url: settings.mcp_url });
        pushToast("success", "Outcome updated.");
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
        await apiDeleteOutcome(outcomeId, settings.mcp_url);
        pushToast("success", "Outcome removed.");
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
        await apiDeleteEvidence(evidenceId, settings.mcp_url);
        pushToast("success", "Evidence removed.");
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
      await apiPromoteEvidence(evidenceId, { ...payload, mcp_url: settings.mcp_url });
      pushToast("success", `Promoted the evidence to a ${payload.target}.`);
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
      setFocusedSubject({ kind, id });
      const panel = PANEL_FOR_SUBJECT[kind];
      if (panel) {
        openPanel(panel);
      }
    },
    [markSignalAsRead, openPanel],
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

  const stopStreaming = useCallback(() => {
    abortRef.current?.abort();
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
      if ((!trimmed && attachments.length === 0) || streaming) {
        return;
      }

      // The sidecar is confirmed down: don't start a doomed stream. The notice
      // above the composer already explains what's wrong; just surface a quiet
      // heads-up in-thread and stop.
      if (sidecarReachable === false) {
        pushNotice("The studio sidecar isn't running — live replies are paused. Start it from Settings.");
        return;
      }

      const userMessage: ChatMessage = existingUserMessage ?? {
        id: crypto.randomUUID(),
        parentId: base.length ? base[base.length - 1].id : null,
        role: "user",
        content: trimmed,
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
        { id: assistantId, parentId: userMessage.id, role: "assistant", content: "", parts: [] },
      ]);
      setStreaming(true);
      setThinkingPhase("health_check");
      setOfflineReply(false);
      setToolActivity([]);

      const controller = new AbortController();
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
              setOfflineReply(true);
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
        setStreaming(false);
        setThinkingPhase(null);
        abortRef.current = null;
      }
    },
    [
      streaming,
      settings,
      brief,
      conversationId,
      refreshCanvas,
      refreshConnectors,
      sidecarReachable,
      pushNotice,
    ],
  );

  const sendMessage = useCallback(
    (text: string, attachments: ChatAttachment[] = []) => runTurn(messages, text, attachments),
    [messages, runTurn],
  );

  /**
   * The turn after `messageId` is regenerated as a sibling, so the previous
   * answer is still there behind the branch picker.
   */
  const regenerateFrom = useCallback(
    async (messageId: string | null) => {
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
    [messages, runTurn],
  );

  const editFrom = useCallback(
    async (messageId: string | null, text: string, attachments: ChatAttachment[] = []) => {
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
    [messages, runTurn],
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

  const clearChat = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setMessages([]);
    setToolActivity([]);
    setStreaming(false);
    setThinkingPhase(null);
    setOfflineReply(false);
    setConversationId(null);
    void apiCreateConversation()
      .then((conversation) =>
        setConversationId((current) => current ?? conversation.id),
      )
      .catch(() => undefined);
  }, []);

  // Initial hydration: env defaults, canvas, health probes.
  useEffect(() => {
    let cancelled = false;

    async function boot() {
      try {
        const defaults = await fetchConfig();
        if (!cancelled) {
          setSidecarReachable(true);
          if (localStorage.getItem(SETTINGS_KEY) === null) {
            saveSettings(defaults);
          }
        }
      } catch {
        if (!cancelled) {
          setSidecarReachable(false);
        }
      }
      if (cancelled) {
        return;
      }
      void refreshCapabilities();
      void refreshCanvas();
      void refreshConnectors();
      void refreshPresets();
      void refreshFeatured();
      void refreshMemory();
      void fetchLatestConversation()
        .then(async ({ conversation }) => {
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
        })
        .catch(() => undefined);
      void healthMcp(settings.mcp_url)
        .then((result) => {
          if (!cancelled) {
            setMcpReachable(result.reachable);
          }
        })
        .catch(() => undefined);
      void healthLlm({
        base_url: settings.base_url,
        api_key: settings.api_key,
        model: settings.model_name,
      })
        .then((result) => {
          if (!cancelled) {
            setLlmHealth(result);
          }
        })
        .catch(() => undefined);
    }

    void boot();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Health polling: the studio must notice that the model or the MCP server
  // came back without a reload, so the bar leaves "Local mode" on its own.
  useEffect(() => {
    const poll = () => {
      if (document.visibilityState === "visible") {
        void checkConnections();
      }
    };

    const timer = window.setInterval(poll, HEALTH_POLL_INTERVAL_MS);
    document.addEventListener("visibilitychange", poll);

    return () => {
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", poll);
    };
  }, [checkConnections]);

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
      models,
      modelsLoading,
      modelsMessage,
      refreshModels,
      mcpReachable,
      sidecarReachable,
      dismissedSidecarNotice,
      dismissSidecarNotice,
      recheckConnections,
      checkConnections,
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
      clearChat,
      conversationId,
      memory,
      memoryLoading,
      refreshMemory,
      addObservation,
      updateObservation,
      deleteObservation,
      clearMemory,
      pushNotice,
      offlineReply,
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
      toasts,
      pushToast,
      dismissToast,
      connectors,
      connectorsError,
      capabilities,
      presets,
      presetError,
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
      focusedSubject,
      focusedJobId,
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
      models,
      modelsLoading,
      modelsMessage,
      refreshModels,
      mcpReachable,
      sidecarReachable,
      dismissedSidecarNotice,
      dismissSidecarNotice,
      recheckConnections,
      checkConnections,
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
      clearChat,
      conversationId,
      memory,
      memoryLoading,
      refreshMemory,
      addObservation,
      updateObservation,
      deleteObservation,
      clearMemory,
      pushNotice,
      offlineReply,
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
      toasts,
      pushToast,
      dismissToast,
      connectors,
      connectorsError,
      capabilities,
      presets,
      presetError,
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
      focusedSubject,
      focusedJobId,
      focusedEvidenceId,
      focusEvidence,
    ],
  );

  return <StudioContext.Provider value={value}>{children}</StudioContext.Provider>;
}

export function useStudio(): StudioContextValue {
  const context = useContext(StudioContext);
  if (!context) {
    throw new Error("useStudio must be used within a StudioProvider");
  }
  return context;
}
