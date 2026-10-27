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
  deleteOutcome as apiDeleteOutcome,
  deleteStep as apiDeleteStep,
  fetchCanvas,
  fetchConfig,
  fetchConnectorCatalog,
  fetchConnectors,
<<<<<<< HEAD
  fetchConversationTree as apiFetchConversationTree,
||||||| fcf59923
=======
  fetchConversationTree,
>>>>>>> origin/main
  fetchLatestConversation,
  fetchMemory,
  fetchModels,
  healthLlm,
  healthMcp,
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
  ChatAttachment,
  AddOutcomePayload,
  AddStepPayload,
  CanvasData,
  CanvasState,
  ChatAttachment,
  ChatMessage,
  ChatPart,
  ConnectorListItem,
  ConnectorPreset,
  ConversationTree,
  Observation,
  StudioBrief,
  StudioConfig,
  StudioError,
  StudioNotification,
<<<<<<< HEAD
  ToolStatus,
  TurnNode,
||||||| fcf59923
=======
  StudioTheme,
  Thesis,
  ToolStatus,
  TurnNode,
>>>>>>> origin/main
  WorkspacePanelId,
} from "../types";
import { catalogManifest } from "../ui/catalog";
import { parseUiSpec } from "../ui/protocol";

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
    return [
      {
        id: node.id,
        parentId: node.parent_id,
        role: node.role,
        content,
        parts: content ? [{ kind: "text" as const, text: content }] : [],
      },
    ];
  });
}

/** Read the failure the sidecar reported on an SSE `error` event. */
function readStudioError(raw: unknown): StudioError {
  if (raw && typeof raw === "object" && "code" in raw) {
    const error = raw as Partial<StudioError>;
    return {
      code: String(error.code ?? "internal"),
      message: String(error.message ?? "The assistant could not finish this turn."),
      detail: error.detail ?? null,
      suggestion: error.suggestion ?? null,
      retryable: Boolean(error.retryable),
      request_id: error.request_id ?? null,
    };
  }
  return {
    code: "internal",
    message: "The assistant could not finish this turn.",
    retryable: true,
  };
}

const SETTINGS_KEY = "studio.settings";
const CANVAS_KEY = "studio.canvas";
const DISPLAY_NAME_KEY = "studio.displayName";
const BRIEF_KEY = "studio.brief";
const SETUP_DISMISSED_KEY = "studio.setupDismissed";
const SIDECAR_NOTICE_DISMISSED_KEY = "studio.sidecarNoticeDismissed";
const NOTIFICATIONS_KEY = "studio.notifications";
const THESES_KEY = "studio.theses";

/** How often the studio re-probes the model and the MCP server. */
const HEALTH_POLL_INTERVAL_MS = 30_000;

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

const SEED_NOTIFICATIONS: StudioNotification[] = [
  {
    id: "NOTIF-101",
    title: "Opportunity Score Shift Identified",
    message: "Minimize time to propagate secrets (O-1) opportunity score reached 15.3 (High Priority).",
    category: "outcome",
    timestamp: new Date(Date.now() - 10 * 60 * 1000).toISOString(),
    read: false,
    targetPanel: "landscape",
    targetId: "O-1",
    actionText: "View Landscape",
    chatPrompt: "How can we address the high opportunity score for secret propagation?",
  },
  {
    id: "NOTIF-102",
    title: "Friction Collapse Simulation Complete",
    message: "Background simulation calculated a 68% deployment velocity increase upon automation.",
    category: "simulation",
    timestamp: new Date(Date.now() - 45 * 60 * 1000).toISOString(),
    read: false,
    actionText: "Talk it through",
    chatPrompt: "Summarize the friction collapse simulation results.",
  },
  {
    id: "NOTIF-103",
    title: "New Customer Telemetry Signal",
    message: "Evidence ingested: 'Config key mismatches account for 40% of deployment rollbacks'.",
    category: "evidence",
    timestamp: new Date(Date.now() - 120 * 60 * 1000).toISOString(),
    read: true,
    targetPanel: "evidence",
    actionText: "View Evidence",
    chatPrompt: "What evidence do we have regarding deployment config errors?",
  },
];

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
  /** Why there is no catalog, when the provider would not list one. */
  modelsMessage: string | null;
  /** Re-ask the endpoint, optionally with unsaved connection settings. */
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
  /** The sidecar's stage for the live turn: health_check, mcp_tools, model. */
  thinkingPhase: string | null;
<<<<<<< HEAD
  sendMessage: (
    text: string,
    attachments?: ChatAttachment[],
    /** Re-ask from this turn: it and everything after it are replaced. */
    options?: { from?: string },
  ) => Promise<void>;
  /** Re-answer the turn ending at `messageId`, as a sibling branch. */
  regenerateFrom: (messageId: string | null) => Promise<void>;
  /** Replace the user turn at `messageId`, as a sibling branch. */
  editFrom: (messageId: string | null, text: string, attachments?: ChatAttachment[]) => Promise<void>;
  /** Take `branch` as the visible path and record it as the conversation head. */
  switchBranch: (messages: ChatMessage[]) => void;
  /** Answer a paused write. The turn resumes on the stream it came from. */
  respondToApproval: (approvalId: string, approved: boolean, reason?: string) => Promise<void>;
  /** Replay a persisted conversation's visible branch as the local transcript. */
  fetchConversationTree: (conversationId: string) => Promise<ConversationTree>;
  /** Record which branch of a conversation is visible. */
  setConversationHead: (conversationId: string, headId: string | null) => Promise<void>;
||||||| fcf59923
  toolActivity: ToolActivity[];
  sendMessage: (text: string) => Promise<void>;
=======
  sendMessage: (text: string, attachments?: ChatAttachment[]) => Promise<void>;
  /** Re-answer the turn that follows `messageId`, as a sibling branch. */
  regenerateFrom: (messageId: string | null) => Promise<void>;
  /** Replace the user turn before `messageId`, as a sibling branch. */
  editFrom: (messageId: string | null, text: string, attachments?: ChatAttachment[]) => Promise<void>;
  /** Take the branch the runtime switched to as the visible conversation. */
  switchBranch: (messages: ChatMessage[]) => void;
  /** Answer a paused write. The turn resumes on its own stream. */
  respondToApproval: (approvalId: string, approved: boolean, reason?: string) => Promise<void>;
>>>>>>> origin/main
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
  /** Scored outcomes saved as shareable opportunity theses. */
  theses: Thesis[];
  saveThesis: (thesis: Omit<Thesis, "id" | "created_at">) => void;
  deleteThesis: (thesisId: string) => void;
  notifications: StudioNotification[];
  unreadNotificationCount: number;
  markNotificationAsRead: (id: string) => void;
  markAllNotificationsAsRead: () => void;
  dismissNotification: (id: string) => void;
  addNotification: (notification: Omit<StudioNotification, "id" | "timestamp" | "read">) => void;
  simulateBackgroundEvent: () => void;
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

function loadSetupDismissed(): boolean {
  try {
      return localStorage.getItem(SETUP_DISMISSED_KEY) === "1";
  } catch {
    return false;
  }
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

function loadNotifications(): StudioNotification[] {
  try {
    const raw = localStorage.getItem(NOTIFICATIONS_KEY);
    if (raw) {
      return JSON.parse(raw) as StudioNotification[];
    }
  } catch {
    /* ignore malformed cache */
  }
  return SEED_NOTIFICATIONS;
}

export function StudioProvider({ children }: { children: ReactNode }) {
  const [settings, setSettings] = useState<StudioConfig>(loadSettings);
  const theme: StudioTheme = settings.theme === "light" ? "light" : "dark";
  const [displayName, setDisplayNameState] = useState<string>(loadDisplayName);
  const [brief, setBrief] = useState<StudioBrief | null>(loadBrief);
  const [setupOpen, setSetupOpen] = useState<boolean>(
    () => loadBrief() === null && !loadSetupDismissed(),
  );
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
  const [activePanel, setActivePanel] = useState<WorkspacePanelId | null>(null);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [connectors, setConnectors] = useState<ConnectorListItem[]>([]);
  const [presets, setPresets] = useState<ConnectorPreset[]>([]);
  const [presetError, setPresetError] = useState<StudioError | null>(null);
  const [connectorsError, setConnectorsError] = useState<StudioError | null>(null);
  const [capabilities, setCapabilities] = useState<Capability[]>([]);
  const [connectorSuggestions, setConnectorSuggestions] = useState<string[]>([]);
  const [notifications, setNotifications] = useState<StudioNotification[]>(loadNotifications);
  const [theses, setTheses] = useState<Thesis[]>(loadTheses);
  const toastId = useRef(0);
  const abortRef = useRef<AbortController | null>(null);

  const saveNotifications = useCallback((items: StudioNotification[]) => {
    setNotifications(items);
    try {
      localStorage.setItem(NOTIFICATIONS_KEY, JSON.stringify(items));
    } catch {
      /* storage unavailable */
    }
  }, []);

  const unreadNotificationCount = useMemo(
    () => notifications.filter((n) => !n.read).length,
    [notifications],
  );

  const markNotificationAsRead = useCallback(
    (id: string) => {
      const next = notifications.map((n) => (n.id === id ? { ...n, read: true } : n));
      saveNotifications(next);
    },
    [notifications, saveNotifications],
  );

  const markAllNotificationsAsRead = useCallback(() => {
    const next = notifications.map((n) => ({ ...n, read: true }));
    saveNotifications(next);
  }, [notifications, saveNotifications]);

  const dismissNotification = useCallback(
    (id: string) => {
      const next = notifications.filter((n) => n.id !== id);
      saveNotifications(next);
    },
    [notifications, saveNotifications],
  );

  const addNotification = useCallback(
    (item: Omit<StudioNotification, "id" | "timestamp" | "read">) => {
      const newNotif: StudioNotification = {
        ...item,
        id: `NOTIF-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
        timestamp: new Date().toISOString(),
        read: false,
      };
      saveNotifications([newNotif, ...notifications]);
    },
    [notifications, saveNotifications],
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

  const simulateBackgroundEvent = useCallback(() => {
    const events: Array<Omit<StudioNotification, "id" | "timestamp" | "read">> = [
      {
        title: "Telemetry Ingestion Complete",
        message: "Analyzed workflow traces: 82% of users report friction during cluster config.",
        category: "evidence",
        targetPanel: "evidence",
        actionText: "Review Evidence",
        chatPrompt: "What friction was reported during cluster config?",
      },
      {
        title: "New Opportunity Uncovered",
        message: "Automating validation rules elevated satisfaction target by +2.4 points.",
        category: "outcome",
        targetPanel: "landscape",
        actionText: "Explore Landscape",
        chatPrompt: "Show me details on the validation rules opportunity.",
      },
      {
        title: "AI Job Step Insight",
        message: "Suggested adding 'Verify secret parity across clusters' to Phase 4 of Job Map.",
        category: "job",
        targetPanel: "jobmap",
        actionText: "Open Job Map",
        chatPrompt: "Why is verifying secret parity across clusters recommended?",
      },
    ];

    const chosen = events[Math.floor(Math.random() * events.length)];
    addNotification(chosen);
    pushToast("info", `Background Activity: ${chosen.title}`);
  }, [addNotification, pushToast]);

<<<<<<< HEAD
  const saveSettings = useCallback(
    (config: StudioConfig) => {
      const movedEndpoint =
        config.base_url !== settings.base_url || config.api_key !== settings.api_key;
      setSettings(config);
      try {
        localStorage.setItem(SETTINGS_KEY, JSON.stringify(config));
      } catch {
        /* storage unavailable */
      }
      // A new endpoint serves a different catalog; ask it before the reader
      // opens the picker and sees the old one.
      if (movedEndpoint) {
        void refreshModels({ base_url: config.base_url, api_key: config.api_key });
      }
    },
    [settings.base_url, settings.api_key, refreshModels],
  );
||||||| fcf59923
  const saveSettings = useCallback((config: StudioConfig) => {
    setSettings(config);
    try {
      localStorage.setItem(SETTINGS_KEY, JSON.stringify(config));
    } catch {
      /* storage unavailable */
    }
  }, []);
=======
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
>>>>>>> origin/main

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
      localStorage.removeItem(SETUP_DISMISSED_KEY);
    } catch {
      /* storage unavailable */
    }
  }, []);

  const openSetup = useCallback(() => {
    setActivePanel(null);
    setSetupOpen(true);
    try {
      localStorage.removeItem(SETUP_DISMISSED_KEY);
    } catch {
      /* storage unavailable */
    }
  }, []);

  const closeSetup = useCallback(() => {
    setSetupOpen(false);
    try {
      localStorage.setItem(SETUP_DISMISSED_KEY, "1");
    } catch {
      /* storage unavailable */
    }
  }, []);

<<<<<<< HEAD
const pushNotice = useCallback((text: string) => {
  setMessages((prev) => [
    ...prev,
    { role: "notice", id: crypto.randomUUID(), parentId: null, content: text },
  ]);
}, []);
||||||| fcf59923
  const pushNotice = useCallback((text: string) => {
    setMessages((prev) => [...prev, { role: "notice", content: text }]);
  }, []);
=======
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
>>>>>>> origin/main

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
  }, [settings.mcp_url]);

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

  const stopStreaming = useCallback(() => {
    abortRef.current?.abort();
  }, []);

<<<<<<< HEAD
  /**
   * Stream one assistant turn. `base` is the history sent to the model; when
   * `userTurn` is given it is appended to that history, otherwise the last
   * message of `base` is the turn being re-answered. The new assistant turn is
   * parented to `assistantParentId`, which is how branches stay linked.
   */
  const runTurn = useCallback(
    async (
      base: ChatMessage[],
      userTurn: ChatMessage | null,
      assistantParentId: string,
    ) => {
      if (streaming) {
||||||| fcf59923
  const sendMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || streaming) {
=======
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
>>>>>>> origin/main
        return;
      }

<<<<<<< HEAD
      const history: ChatMessage[] = userTurn ? [...base, userTurn] : base;

      const assistantId = crypto.randomUUID();
      const assistantIndex = history.length;
      setMessages([
        ...history,
        { role: "assistant", id: assistantId, parentId: assistantParentId, content: "", parts: [] },
      ]);
||||||| fcf59923
      const history: ChatMessage[] = [...messages, { role: "user", content: trimmed }];
      const assistantIndex = history.length;
      setMessages([...history, { role: "assistant", content: "", parts: [] }]);
=======
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
      const history: ChatMessage[] =
        existingUserMessage && base.at(-1)?.id === existingUserMessage.id
          ? base
          : [...base, userMessage];

      setMessages([
        ...history,
        { id: assistantId, parentId: userMessage.id, role: "assistant", content: "", parts: [] },
      ]);
>>>>>>> origin/main
      setStreaming(true);
      setThinkingPhase("health_check");
      setOfflineReply(false);

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

      // The turn owns its own timeline, so a finished run stays inspectable and
      // the next turn starts from nothing without a reset elsewhere.
      const publish = () => {
<<<<<<< HEAD
        setMessages((prev) => {
          if (prev.length <= assistantIndex) {
            return prev;
          }
          const next = [...prev];
          const retryText = userTurn?.content ?? base[base.length - 1]?.content ?? "";
          next[assistantIndex] = {
            role: "assistant",
            id: assistantId,
            parentId: assistantParentId,
            content,
            parts: [...parts],
            ...(failure ? { error: failure, retryText } : {}),
            ...(stopped ? { stopped: true, retryText } : {}),
          };
          return next;
        });
||||||| fcf59923
        setMessages((prev) => {
          const next = [...prev];
          next[assistantIndex] = {
            role: "assistant",
            content,
            parts: [...parts],
            ...(failure ? { error: failure, retryText: trimmed } : {}),
          };
          return next;
        });
=======
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
>>>>>>> origin/main
      };

      const handleEvent = (event: RawSseEvent) => {
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
<<<<<<< HEAD
          case "tool": {
            const name = String(event.data.name ?? "");
            const status = String(event.data.status ?? "");
            const mapped: ToolStatus =
              status === "ok" || status === "error" || status === "declined" ? status : "running";
            const open = parts
              .slice()
              .reverse()
              .find(
                (part): part is Extract<ChatPart, { kind: "tool" }> =>
                  part.kind === "tool" && part.name === name && part.status === "running",
              );
            if (mapped === "running") {
              if (open) {
                break;
              }
              parts = [...parts, { kind: "tool", id: `tool-${Date.now()}`, name, status: mapped }];
            } else if (open) {
              parts = [
                ...parts.filter((part) => part !== open),
                { ...open, status: mapped, approval: undefined },
              ];
            } else {
              parts = [...parts, { kind: "tool", id: `tool-${Date.now()}`, name, status: mapped }];
            }
            publish();
||||||| fcf59923
          case "tool":
            setToolActivity((prev) => [
              ...prev,
              {
                name: String(event.data.name ?? ""),
                status: String(event.data.status ?? ""),
                preview: event.data.preview ? String(event.data.preview) : undefined,
              },
            ]);
=======
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
>>>>>>> origin/main
            break;
          }
          case "message": {
            terminal = true;
            // The terminal frame is authoritative for the prose, but it must
            // never erase structured parts: thinking, tool calls, citations,
            // and surfaces sit between the paragraphs that frame them.
            content = String(event.data.content ?? content);
            if (content && !parts.some((part) => part.kind === "text")) {
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
<<<<<<< HEAD
                { role: "notice", id: crypto.randomUUID(), parentId: null, content: `Connector failed: ${reason}` },
||||||| fcf59923
                { role: "notice", content: `Connector failed: ${reason}` },
=======
                {
                  id: crypto.randomUUID(),
                  parentId: assistantId,
                  role: "notice",
                  content: `Connector failed: ${reason}`,
                },
>>>>>>> origin/main
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
          // An abort is the user's own doing, so it is not a failure — but it is
          // still a fact about the turn. Keep what arrived, stop any tool that
          // was mid-flight, and leave the turn in place so the transcript says
          // what happened instead of silently losing the question.
          stopped = true;
<<<<<<< HEAD
          parts = parts.map((part) =>
            part.kind === "tool" && part.status === "running"
              ? { ...part, status: "error" as ToolStatus }
              : part,
          );
          publish();
||||||| fcf59923
          setMessages((prev) => {
            const next = [...prev];
            if (next.length && next[next.length - 1].role === "assistant" && !next[next.length - 1].content) {
              next.pop();
            }
            return next;
          });
=======
          setMessages((prev) =>
            prev.filter((message) => message.id !== assistantId || message.content !== ""),
          );
>>>>>>> origin/main
        } else {
          terminal = true;
          failure = asStudioError(error);
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
          publish();
        }
        setStreaming(false);
        setThinkingPhase(null);
        abortRef.current = null;
      }
    },
<<<<<<< HEAD
    [streaming, settings, brief, conversationId, refreshCanvas, refreshConnectors],
  );

  const sendMessage = useCallback(
    async (
      text: string,
      attachments: ChatAttachment[] = [],
      options: { from?: string } = {},
    ) => {
      const trimmed = text.trim();
      if ((!trimmed && !attachments.length) || streaming) {
        return;
      }

      // A re-ask replaces the turn it starts from: the old question and the
      // answer it got are the same turn, and keeping both would read as a
      // conversation the reader never had.
      const cut = options.from
        ? messages.findIndex((message) => message.id === options.from)
        : -1;
      const replaced = cut >= 0 ? messages.slice(0, cut) : messages;

      // Files ride only on the newest turn. Re-sending megabytes of base64 with
      // every later question would make each turn slower than the last.
      const history: ChatMessage[] = replaced.map((message) =>
        message.attachments
          ? {
              id: message.id,
              parentId: message.parentId,
              role: message.role,
              content: message.content,
              parts: message.parts,
            }
          : message,
      );
      const userMessage: ChatMessage = {
        id: crypto.randomUUID(),
        parentId: history.length ? history[history.length - 1].id : null,
        role: "user",
        content: trimmed,
        ...(attachments.length ? { attachments: attachments as unknown as ChatAttachment[] } : {}),
      };
      await runTurn(history, userMessage, userMessage.id);
    },
    [messages, streaming, runTurn],
  );

  /**
   * Re-answer the turn ending at `messageId`: everything up to and including
   * that message stays, and a new assistant branch grows from it.
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
      const base = messages.slice(0, questionIndex + 1);
      await runTurn(base, null, base[base.length - 1].id);
    },
    [messages, runTurn],
  );

  /**
   * Replace the user turn at `messageId` with edited words, at its original
   * parent, and grow a new assistant branch from it.
   */
  const editFrom = useCallback(
    async (messageId: string | null, text: string, attachments: ChatAttachment[] = []) => {
      const cut = messageId === null ? messages.length - 1 : messages.findIndex((message) => message.id === messageId);
      if (cut < 0 || streaming) {
        return;
      }
      const original = messages[cut];
      const base = messages.slice(0, cut);
      const trimmed = text.trim();
      const edited: ChatMessage = {
        id: original.id,
        parentId: original.parentId ?? null,
        role: "user",
        content: trimmed,
        ...(attachments.length ? { attachments } : { attachments: original.attachments }),
      };
      await runTurn(base, edited, edited.id);
    },
    [messages, streaming, runTurn],
  );

  /**
   * Take `branch` as the visible path and record it as the conversation head,
   * so a reload reopens the branch that was visible.
   */
  const switchBranch = useCallback(
    (branch: ChatMessage[]) => {
      setMessages(branch);
      const head = branch.length ? branch[branch.length - 1].id : null;
      if (conversationId) {
        void apiSetConversationHead(conversationId, head).catch(() => undefined);
      }
    },
    [conversationId],
  );

  /**
   * Answer a paused write. The turn resumes on the stream it came from.
   */
  const respondToApproval = useCallback(
    async (approvalId: string, approved: boolean, reason = "") => {
      try {
        await apiResolveApproval(approvalId, approved, reason);
      } catch {
        pushToast("error", "That approval request is no longer waiting.");
      }
    },
    [pushToast],
  );

  /**
   * Replay a persisted conversation's visible branch as the local transcript.
   */
  const fetchConversationTree = useCallback(
    async (conversationId: string): Promise<ConversationTree> => {
      const tree = await apiFetchConversationTree(conversationId);
      setConversationId(tree.conversation.id);
      setMessages(
        tree.messages
          .filter((node: TurnNode) => node.role === "user" || node.role === "assistant")
          .map((node: TurnNode) => ({
            id: node.id,
            parentId: node.parent_id,
            role: node.role as "user" | "assistant",
            content: node.content ?? "",
            parts: node.content ? [{ kind: "text", text: node.content }] : [],
          })),
      );
      return tree;
    },
    [],
  );

  /** Record which branch of a conversation is visible. */
  const setConversationHead = useCallback(
    async (conversationId: string, headId: string | null) => {
      await apiSetConversationHead(conversationId, headId);
    },
    [],
||||||| fcf59923
    [
      messages,
      streaming,
      settings,
      brief,
      conversationId,
      refreshCanvas,
      refreshConnectors,
    ],
=======
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
>>>>>>> origin/main
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
      } catch {
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
    } catch {
      pushToast("error", "I couldn't clear what I've learned.");
    }
  }, [pushToast]);

  const clearChat = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setMessages([]);
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
      void refreshModels();
      void refreshMemory();
      void fetchLatestConversation()
        .then(async ({ conversation }) => {
          if (cancelled || !conversation) {
            return;
          }
          setConversationId(conversation.id);
<<<<<<< HEAD
          setMessages(
            turns
              .filter((turn) => turn.role === "user" || turn.role === "assistant")
              .map((turn) => ({
                id: `saved-${turn.id}`,
                parentId: null,
                role: turn.role as "user" | "assistant",
                content: turn.content,
                parts: turn.content ? [{ kind: "text" as const, text: turn.content }] : [],
              })),
          );
||||||| fcf59923
          setMessages(
            turns
              .filter((turn) => turn.role === "user" || turn.role === "assistant")
              .map((turn) => ({
                role: turn.role as "user" | "assistant",
                content: turn.content,
                parts: turn.content ? [{ kind: "text", text: turn.content }] : [],
              })),
          );
=======
          // The tree, not the flat turn list: a conversation with branches
          // must open on the branch that was visible when it was left.
          const tree = await fetchConversationTree(conversation.id);
          if (cancelled) {
            return;
          }
          setMessages(turnsToMessages(tree.messages, tree.head_id));
>>>>>>> origin/main
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
      sendMessage,
<<<<<<< HEAD
      regenerateFrom,
      editFrom,
      switchBranch,
      respondToApproval,
      fetchConversationTree,
      setConversationHead,
||||||| fcf59923
=======
      regenerateFrom,
      editFrom,
      switchBranch,
      respondToApproval,
>>>>>>> origin/main
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
      createJob,
      updateJob,
      deleteJob,
      updateStep,
      deleteStep,
      updateOutcome,
      deleteOutcome,
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
      theses,
      saveThesis,
      deleteThesis,
      notifications,
      unreadNotificationCount,
      markNotificationAsRead,
      markAllNotificationsAsRead,
      dismissNotification,
      addNotification,
      simulateBackgroundEvent,
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
      sendMessage,
<<<<<<< HEAD
      regenerateFrom,
      editFrom,
      switchBranch,
      respondToApproval,
      fetchConversationTree,
      setConversationHead,
||||||| fcf59923
=======
      regenerateFrom,
      editFrom,
      switchBranch,
      respondToApproval,
>>>>>>> origin/main
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
      createJob,
      updateJob,
      deleteJob,
      updateStep,
      deleteStep,
      updateOutcome,
      deleteOutcome,
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
      theses,
      saveThesis,
      deleteThesis,
      notifications,
      unreadNotificationCount,
      markNotificationAsRead,
      markAllNotificationsAsRead,
      dismissNotification,
      addNotification,
      simulateBackgroundEvent,
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
