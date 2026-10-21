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
  addOutcome as apiAddOutcome,
  addStep as apiAddStep,
  createJob as apiCreateJob,
  deleteJob as apiDeleteJob,
  deleteOutcome as apiDeleteOutcome,
  deleteStep as apiDeleteStep,
  fetchCanvas,
  fetchConfig,
  healthLlm,
  healthMcp,
  streamChat,
  updateJob as apiUpdateJob,
  updateOutcome as apiUpdateOutcome,
  updateStep as apiUpdateStep,
} from "../api/studioApi";
import type { RawSseEvent } from "../api/sse";
import type {
  AddOutcomePayload,
  AddStepPayload,
  CanvasData,
  ChatMessage,
  ChatPart,
  StudioBrief,
  StudioConfig,
  WorkspacePanelId,
} from "../types";
import { catalogManifest } from "../ui/catalog";
import { parseUiSpec } from "../ui/protocol";

const SETTINGS_KEY = "studio.settings";
const CANVAS_KEY = "studio.canvas";
const DISPLAY_NAME_KEY = "studio.displayName";
const BRIEF_KEY = "studio.brief";
const SETUP_DISMISSED_KEY = "studio.setupDismissed";

export const EMPTY_CONFIG: StudioConfig = {
  base_url: "http://localhost:8001/v1",
  api_key: "local",
  model_name: "local-tools-model",
  mcp_url: "http://localhost:8000/mcp",
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
  refreshCanvas: () => Promise<void>;
  llmHealth: { healthy: boolean | null; message: string };
  mcpReachable: boolean;
  messages: ChatMessage[];
  streaming: boolean;
  thinkingPhase: string | null;
  toolActivity: ToolActivity[];
  sendMessage: (text: string) => Promise<void>;
  stopStreaming: () => void;
  clearChat: () => void;
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
  pendingSimOutcome: string | null;
  requestSimulate: (outcomeId: string) => void;
  clearPendingSimOutcome: () => void;
  activePanel: WorkspacePanelId | null;
  openPanel: (panel: WorkspacePanelId) => void;
  closePanel: () => void;
  toasts: Toast[];
  pushToast: (kind: ToastKind, message: string) => void;
  dismissToast: (id: number) => void;
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

export function StudioProvider({ children }: { children: ReactNode }) {
  const [settings, setSettings] = useState<StudioConfig>(loadSettings);
  const [displayName, setDisplayNameState] = useState<string>(loadDisplayName);
  const [brief, setBrief] = useState<StudioBrief | null>(loadBrief);
  const [setupOpen, setSetupOpen] = useState<boolean>(
    () => loadBrief() === null && !loadSetupDismissed(),
  );
  const [offlineReply, setOfflineReply] = useState(false);
  const [canvas, setCanvas] = useState<CanvasData | null>(loadCanvasCache);
  const [canvasLoading, setCanvasLoading] = useState(false);
  const [canvasCached, setCanvasCached] = useState(() => loadCanvasCache() !== null);
  const [llmHealth, setLlmHealth] = useState<{ healthy: boolean | null; message: string }>({
    healthy: null,
    message: "Health not checked yet.",
  });
  const [mcpReachable, setMcpReachable] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [thinkingPhase, setThinkingPhase] = useState<string | null>(null);
  const [toolActivity, setToolActivity] = useState<ToolActivity[]>([]);
  const [pendingSimOutcome, setPendingSimOutcome] = useState<string | null>(null);
  const [activePanel, setActivePanel] = useState<WorkspacePanelId | null>(null);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const toastId = useRef(0);
  const abortRef = useRef<AbortController | null>(null);

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

  // Skipping is a real choice: record it so the conversation does not reappear
  // on reload, while the hero and drawer keep a quiet nudge available.
  const closeSetup = useCallback(() => {
    setSetupOpen(false);
    try {
      localStorage.setItem(SETUP_DISMISSED_KEY, "1");
    } catch {
      /* storage unavailable */
    }
  }, []);

  const pushNotice = useCallback((text: string) => {
    setMessages((prev) => [...prev, { role: "notice", content: text }]);
  }, []);

  const refreshCanvas = useCallback(async () => {
    setCanvasLoading(true);
    try {
      const data = await fetchCanvas(settings.mcp_url);
      setCanvas(data);
      setCanvasCached(false);
      try {
        localStorage.setItem(CANVAS_KEY, JSON.stringify(data));
      } catch {
        /* storage unavailable */
      }
    } catch (error) {
      pushToast("error", `Canvas sync failed: ${(error as Error).message}`);
    } finally {
      setCanvasLoading(false);
    }
  }, [settings.mcp_url, pushToast]);

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
      try {
        await apiAddOutcome({ ...payload, mcp_url: settings.mcp_url });
        pushToast("success", "Outcome captured successfully!");
        await refreshCanvas();
      } catch (error) {
        pushToast("error", `Error capturing outcome: ${(error as Error).message}`);
      }
    },
    [settings.mcp_url, pushToast, refreshCanvas],
  );

  const createJob = useCallback(
    async (payload: { name: string; description?: string }): Promise<string | null> => {
      try {
        const response = await apiCreateJob({ ...payload, mcp_url: settings.mcp_url });
        pushToast("success", `Job created: ${payload.name}`);
        await refreshCanvas();
        if (response.result && typeof response.result === "object") {
          return response.result.id ?? null;
        }
        return null;
      } catch (error) {
        pushToast("error", `Could not create the job: ${(error as Error).message}`);
        return null;
      }
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

  const clearPendingSimOutcome = useCallback(() => setPendingSimOutcome(null), []);

  const closePanel = useCallback(() => setActivePanel(null), []);

  const openPanel = useCallback(
    (panel: WorkspacePanelId) => {
      // Opening a surface is exploring: leave the setup conversation without
      // trapping people back in it when they close the panel. The draft stays.
      if (setupOpen) {
        closeSetup();
      }
      setActivePanel(panel);
    },
    [setupOpen, closeSetup],
  );

  const requestSimulate = useCallback((outcomeId: string) => {
    setPendingSimOutcome(outcomeId);
    setActivePanel("impact");
  }, []);

  const stopStreaming = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  const sendMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || streaming) {
        return;
      }

      const history: ChatMessage[] = [...messages, { role: "user", content: trimmed }];
      setMessages([...history, { role: "assistant", content: "", parts: [] }]);
      setStreaming(true);
      setThinkingPhase("health_check");
      setOfflineReply(false);
      setToolActivity([]);

      const controller = new AbortController();
      abortRef.current = controller;

      let content = "";
      let parts: ChatPart[] = [];

      // Prose is appended to the open text part; a surface opens a new one, so
      // the transcript keeps the agent's order instead of gathering all prose
      // above all cards.
      const appendText = (text: string) => {
        if (!text) {
          return;
        }
        content += text;
        const last = parts[parts.length - 1];
        parts =
          last?.kind === "text"
            ? [...parts.slice(0, -1), { kind: "text", text: last.text + text }]
            : [...parts, { kind: "text", text }];
      };

      const publish = () => {
        setMessages((prev) => {
          const next = [...prev];
          next[next.length - 1] = { role: "assistant", content, parts: [...parts] };
          return next;
        });
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
          case "delta": {
            appendText(String(event.data.text ?? ""));
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
          case "tool":
            setToolActivity((prev) => [
              ...prev,
              {
                name: String(event.data.name ?? ""),
                status: String(event.data.status ?? ""),
                preview: event.data.preview ? String(event.data.preview) : undefined,
              },
            ]);
            break;
          case "message": {
            content = String(event.data.content ?? content);
            const hasSurfaces = parts.some((part) => part.kind === "ui");
            if (!hasSurfaces) {
              parts = content ? [{ kind: "text", text: content }] : [];
            }
            publish();
            break;
          }
          case "canvas_dirty":
            void refreshCanvas();
            break;
          case "error":
            pushToast("error", String(event.data.message ?? "Unknown chat error"));
            break;
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
          },
          handleEvent,
          controller.signal,
        );
      } catch (error) {
        const aborted = (error as Error).name === "AbortError";
        if (!aborted) {
          pushToast("error", `Error during assistant completion: ${(error as Error).message}`);
        }
        if (!content) {
          setMessages((prev) => {
            const next = [...prev];
            if (next.length && next[next.length - 1].content === "") {
              next.pop();
            }
            return next;
          });
        }
      } finally {
        setStreaming(false);
        setThinkingPhase(null);
        abortRef.current = null;
      }
    },
    [messages, streaming, settings, brief, refreshCanvas, pushToast],
  );

  const clearChat = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setMessages([]);
    setToolActivity([]);
    setStreaming(false);
    setThinkingPhase(null);
    setOfflineReply(false);
  }, []);

  // Initial hydration: env defaults, canvas, health probes.
  useEffect(() => {
    let cancelled = false;

    async function boot() {
      try {
        const defaults = await fetchConfig();
        if (!cancelled && localStorage.getItem(SETTINGS_KEY) === null) {
          saveSettings(defaults);
        }
      } catch {
        /* sidecar not reachable; keep local fallback defaults */
      }
      if (cancelled) {
        return;
      }
      void refreshCanvas();
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
      refreshCanvas,
      llmHealth,
      mcpReachable,
      messages,
      streaming,
      thinkingPhase,
      toolActivity,
      sendMessage,
      stopStreaming,
      clearChat,
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
      pendingSimOutcome,
      requestSimulate,
      clearPendingSimOutcome,
      activePanel,
      openPanel,
      closePanel,
      toasts,
      pushToast,
      dismissToast,
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
      refreshCanvas,
      llmHealth,
      mcpReachable,
      messages,
      streaming,
      thinkingPhase,
      toolActivity,
      sendMessage,
      stopStreaming,
      clearChat,
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
      pendingSimOutcome,
      requestSimulate,
      clearPendingSimOutcome,
      activePanel,
      openPanel,
      closePanel,
      toasts,
      pushToast,
      dismissToast,
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
