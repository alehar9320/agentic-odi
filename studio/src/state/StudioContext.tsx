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
  fetchCanvas,
  fetchConfig,
  healthLlm,
  healthMcp,
  streamChat,
} from "../api/studioApi";
import type { RawSseEvent } from "../api/sse";
import type {
  AddOutcomePayload,
  AddStepPayload,
  CanvasData,
  ChatMessage,
  StudioConfig,
} from "../types";

const SETTINGS_KEY = "studio.settings";
const CANVAS_KEY = "studio.canvas";
const ENGAGEMENT_KEY = "studio.engagementLevel";

export const WELCOME_MESSAGE =
  "Welcome to **The Living Studio**. We have eliminated backlogs and Jira spreadsheets.\n\n" +
  "You are looking at a living map of human progress. Tell me what your customers are struggling with, " +
  "or click on any outcome on the canvas to inspect its causality.";

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
  clearChat: () => void;
  addStep: (payload: Omit<AddStepPayload, "mcp_url">) => Promise<void>;
  addOutcome: (payload: Omit<AddOutcomePayload, "mcp_url">) => Promise<void>;
  pendingSimOutcome: string | null;
  requestSimulate: (outcomeId: string) => void;
  clearPendingSimOutcome: () => void;
  activeTab: string;
  setActiveTab: (tab: string) => void;
  engagementLevel: number;
  setEngagementLevel: (level: number) => void;
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

function loadEngagementLevel(): number {
  try {
    const raw = localStorage.getItem(ENGAGEMENT_KEY);
    if (raw) {
      return Math.max(0, Math.min(2, parseInt(raw, 10)));
    }
  } catch {
    /* ignore malformed cache */
  }
  return 0;
}

export function StudioProvider({ children }: { children: ReactNode }) {
  const [settings, setSettings] = useState<StudioConfig>(loadSettings);
  const [canvas, setCanvas] = useState<CanvasData | null>(loadCanvasCache);
  const [canvasLoading, setCanvasLoading] = useState(false);
  const [canvasCached, setCanvasCached] = useState(() => loadCanvasCache() !== null);
  const [engagementLevel, setEngagementLevel] = useState(() => loadEngagementLevel());
  const [llmHealth, setLlmHealth] = useState<{ healthy: boolean | null; message: string }>({
    healthy: null,
    message: "Health not checked yet.",
  });
  const [mcpReachable, setMcpReachable] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([
    { role: "assistant", content: WELCOME_MESSAGE },
  ]);
  const [streaming, setStreaming] = useState(false);
  const [thinkingPhase, setThinkingPhase] = useState<string | null>(null);
  const [toolActivity, setToolActivity] = useState<ToolActivity[]>([]);
  const [pendingSimOutcome, setPendingSimOutcome] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState("landscape");
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

  const saveEngagementLevel = useCallback((level: number) => {
    setEngagementLevel(level);
    try {
      localStorage.setItem(ENGAGEMENT_KEY, String(level));
    } catch {
      /* storage unavailable */
    }
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

  const clearPendingSimOutcome = useCallback(() => setPendingSimOutcome(null), []);

  const requestSimulate = useCallback((outcomeId: string) => {
    setPendingSimOutcome(outcomeId);
    setActiveTab("impact");
  }, []);

  const sendMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || streaming) {
        return;
      }

      const history: ChatMessage[] = [...messages, { role: "user", content: trimmed }];
      setMessages([...history, { role: "assistant", content: "" }]);
      setStreaming(true);
      setThinkingPhase("health_check");
      setToolActivity([]);

      const controller = new AbortController();
      abortRef.current = controller;

      let content = "";

      const handleEvent = (event: RawSseEvent) => {
        switch (event.event) {
          case "status":
            setThinkingPhase(String(event.data.phase ?? ""));
            break;
          case "delta": {
            content += String(event.data.text ?? "");
            setMessages((prev) => {
              const next = [...prev];
              next[next.length - 1] = { role: "assistant", content };
              return next;
            });
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
          case "message":
            content = String(event.data.content ?? content);
            setMessages((prev) => {
              const next = [...prev];
              next[next.length - 1] = { role: "assistant", content };
              return next;
            });
            break;
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
          },
          handleEvent,
          controller.signal,
        );
      } catch (error) {
        if ((error as Error).name !== "AbortError") {
          pushToast("error", `Error during assistant completion: ${(error as Error).message}`);
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
    [messages, streaming, settings, refreshCanvas, pushToast],
  );

  const clearChat = useCallback(() => {
    abortRef.current?.abort();
    setMessages([{ role: "assistant", content: WELCOME_MESSAGE }]);
    setToolActivity([]);
    setStreaming(false);
    setThinkingPhase(null);
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
      clearChat,
      addStep,
      addOutcome,
      pendingSimOutcome,
      requestSimulate,
      clearPendingSimOutcome,
      activeTab,
      setActiveTab,
      engagementLevel,
      setEngagementLevel: saveEngagementLevel,
      toasts,
      pushToast,
      dismissToast,
    }),
    [
      settings,
      saveSettings,
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
      clearChat,
      addStep,
      addOutcome,
      pendingSimOutcome,
      requestSimulate,
      clearPendingSimOutcome,
      activeTab,
      engagementLevel,
      saveEngagementLevel,
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
