import { useEffect } from "react";

import { useOnlineStatus } from "../lib/onlineStatus";
import { useStudio } from "../state/StudioContext";
import { useBanner } from "./BannerProvider";
import type { BannerActionId } from "./types";

/**
 * The reactive half of the banner system.
 *
 * The store knows nothing about the studio; this component is the one place
 * that reads studio state and turns conditions into banners. Because it also
 * clears a banner when its condition goes away, a stale warning cannot linger —
 * the sidecar strip disappears the moment the sidecar answers.
 *
 * Two conditions live here, and the difference between them is the whole point.
 * **Losing a sidecar this session was using** is a failure: the assistant stops
 * and live data stops moving, and the person is owed a way back. **Never having
 * one** is the product working — it says so in place, on the action that needed
 * it, rather than in a strip that blames the studio for shipping as designed.
 */
export function BannerBridge() {
  const { raise, resolve } = useBanner();
  const { sidecarReachable, dismissedSidecarNotice } = useStudio();
  const online = useOnlineStatus();

  useEffect(() => {
    // One sentence when the connection goes, resolved when it comes back. The
    // stable kind means a flapping connection updates this row in place instead
    // of stacking a copy per event, so it is not repeated on every action.
    if (!online) {
      raise({ kind: "offline" });
    } else {
      resolve("offline");
    }
  }, [online, raise, resolve]);

  useEffect(() => {
    // Only a measured loss raises this: `StudioContext` records a negative from
    // a recovery probe just when the sidecar itself witnessed it, or when it
    // contradicts what the studio already believed. A browser-only visitor's
    // reachability therefore stays unknown and nothing is said.
    if (sidecarReachable === false && !dismissedSidecarNotice && online) {
      raise({ kind: "sidecar-down" });
    } else {
      resolve("sidecar-down");
    }
  }, [sidecarReachable, dismissedSidecarNotice, online, raise, resolve]);

  return null;
}

/**
 * Turns a banner button into a studio call, and a dismissal into a durable
 * choice. Imperative actions (recheck, open a panel) resolve here; anything else
 * is sent as the user's next message, so the agent keeps one authority and one
 * audit trail.
 */
export function useBannerActionDispatcher(): {
  onIntent: (intent: string) => void;
  onAction: (action: BannerActionId) => void;
  onDismiss: (id: string) => void;
} {
  const { dismiss } = useBanner();
  const { recheckConnections, openSetup, dismissSidecarNotice, ask } = useStudio();

  function onAction(action: BannerActionId) {
    switch (action) {
      case "recheck-sidecar":
        void recheckConnections();
        break;
      case "open-setup":
        openSetup();
        break;
      case "install-update":
      case "restart":
        // The desktop updater is not wired to banners yet. Nothing is claimed
        // and nothing pretends to happen.
        break;
    }
  }

  function onDismiss(id: string) {
    // Dismissing the sidecar strip is a session-long choice, not just a hidden
    // row: it must survive the next failed probe, or the strip would return.
    if (id === "sidecar-down") {
      dismissSidecarNotice();
    }
    dismiss(id);
  }

  return { onIntent: ask, onAction, onDismiss };
}
