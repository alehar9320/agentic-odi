/* eslint-disable react-refresh/only-export-components -- context module intentionally exports the hooks alongside the provider */
import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

export type ToastKind = "success" | "error" | "info";

export interface Toast {
  id: number;
  kind: ToastKind;
  message: string;
  /** One-off callback, for a toast that can hand back what it just took. */
  action?: { label: string; run: () => void };
  /** How long the toast stays up. Defaults to six seconds. */
  durationMs?: number;
}

export const SIDECAR_NOTICE_DISMISSED_KEY = "studio.sidecarNoticeDismissed";

function loadSidecarNoticeDismissed(): boolean {
  try {
    return localStorage.getItem(SIDECAR_NOTICE_DISMISSED_KEY) === "1";
  } catch {
    return false;
  }
}

/** Subscribes only to the toast list: re-renders when a toast appears or leaves. */
const ToastsContext = createContext<{ toasts: Toast[] } | null>(null);

/** Subscribes only to notices actions: identity-stable, so action-only consumers
 *  do not re-render when the toast list changes. */
const NoticesActionsContext = createContext<{
  pushToast: (
    kind: ToastKind,
    message: string,
    options?: { action?: { label: string; run: () => void }; durationMs?: number },
  ) => number;
  dismissToast: (id: number) => void;
  dismissedSidecarNotice: boolean;
  setDismissedSidecarNotice: (dismissed: boolean) => void;
} | null>(null);

export function NoticesProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [dismissedSidecarNotice, setDismissedSidecarNoticeState] = useState<boolean>(loadSidecarNoticeDismissed());
  const toastId = useRef(0);

  const pushToast = useCallback(
    (
      kind: ToastKind,
      message: string,
      options?: { action?: { label: string; run: () => void }; durationMs?: number },
    ) => {
      const id = (toastId.current += 1);
      setToasts((prev) => [
        ...prev,
        {
          id,
          kind,
          message,
          ...(options?.action ? { action: options.action } : {}),
          ...(options?.durationMs ? { durationMs: options.durationMs } : {}),
        },
      ]);
      window.setTimeout(() => {
        setToasts((prev) => prev.filter((toast) => toast.id !== id));
      }, options?.durationMs ?? 6000);
      return id;
    },
    [],
  );

  const dismissToast = useCallback((id: number) => {
    setToasts((prev) => prev.filter((toast) => toast.id !== id));
  }, []);

  const setDismissedSidecarNotice = useCallback((dismissed: boolean) => {
    setDismissedSidecarNoticeState(dismissed);
    try {
      localStorage.setItem(SIDECAR_NOTICE_DISMISSED_KEY, dismissed ? "1" : "0");
    } catch {
      /* storage unavailable */
    }
  }, []);

  /** Re-renders only when the list actually changes. */
  const toastsValue = useMemo(() => ({ toasts }), [toasts]);
  /** Identity-stable unless a notice is dismissed. */
  const actionsValue = useMemo(
    () => ({ pushToast, dismissToast, dismissedSidecarNotice, setDismissedSidecarNotice }),
    [pushToast, dismissToast, dismissedSidecarNotice, setDismissedSidecarNotice],
  );

  return (
    <ToastsContext.Provider value={toastsValue}>
      <NoticesActionsContext.Provider value={actionsValue}>
        {children}
      </NoticesActionsContext.Provider>
    </ToastsContext.Provider>
  );
}

/** The toast list: re-renders when toasts are added or cleared. */
export function useToasts(): Toast[] {
  const context = useContext(ToastsContext);
  if (!context) {
    throw new Error("useToasts must be used within a NoticesProvider");
  }
  return context.toasts;
}

/** Notices actions: identity-stable across toast pushes. */
export function useNoticesActions() {
  const context = useContext(NoticesActionsContext);
  if (!context) {
    throw new Error("useNoticesActions must be used within a NoticesProvider");
  }
  return context;
}
