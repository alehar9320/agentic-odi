/* eslint-disable react-refresh/only-export-components -- context module intentionally exports the hook and constants alongside the provider */
import { createContext, useContext, useMemo, type ReactNode } from "react";

import type { Toast, ToastKind } from "../StudioContext";

/**
 * Everything a notice can carry: the toast list, the sidecar-down state, and
 * the actions that change them.
 *
 * The list and the actions live in separate contexts so a consumer that only
 * acts (pushToast / dismissToast) does not re-render when a new toast arrives,
 * and a consumer that only reads the list does not re-render when an action
 * identity changes.
 */
export interface NoticesContextValue {
  toasts: Toast[];
  pushToast: (
    kind: ToastKind,
    message: string,
    options?: { action?: { label: string; run: () => void }; durationMs?: number },
  ) => number;
  dismissToast: (id: number) => void;
  sidecarReachable: boolean | null;
  dismissedSidecarNotice: boolean;
  dismissSidecarNotice: () => void;
  recheckConnections: () => Promise<void>;
}

const NoticesListContext = createContext<
  Pick<NoticesContextValue, "toasts" | "sidecarReachable" | "dismissedSidecarNotice"> | null
>(null);

const NoticesActionsContext = createContext<
  Pick<
    NoticesContextValue,
    "pushToast" | "dismissToast" | "dismissSidecarNotice" | "recheckConnections"
  > | null
>(null);

type NoticesProviderProps = {
  children: ReactNode;
} & NoticesContextValue;

export function NoticesProvider({
  children,
  toasts,
  pushToast,
  dismissToast,
  sidecarReachable,
  dismissedSidecarNotice,
  dismissSidecarNotice,
  recheckConnections,
}: NoticesProviderProps) {
  const listValue = useMemo(
    () => ({ toasts, sidecarReachable, dismissedSidecarNotice }),
    [toasts, sidecarReachable, dismissedSidecarNotice],
  );
  const actionsValue = useMemo(
    () => ({ pushToast, dismissToast, dismissSidecarNotice, recheckConnections }),
    [pushToast, dismissToast, dismissSidecarNotice, recheckConnections],
  );
  return (
    <NoticesListContext.Provider value={listValue}>
      <NoticesActionsContext.Provider value={actionsValue}>
        {children}
      </NoticesActionsContext.Provider>
    </NoticesListContext.Provider>
  );
}

export function useNoticesList() {
  const context = useContext(NoticesListContext);
  if (!context) {
    throw new Error("useNoticesList must be used within a NoticesProvider");
  }
  return context;
}

export function useNoticesActions() {
  const context = useContext(NoticesActionsContext);
  if (!context) {
    throw new Error("useNoticesActions must be used within a NoticesProvider");
  }
  return context;
}

export function useNotices(): NoticesContextValue {
  return { ...useNoticesList(), ...useNoticesActions() };
}
