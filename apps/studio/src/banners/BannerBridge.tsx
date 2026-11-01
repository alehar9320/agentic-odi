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
 * Adding a state-driven banner is a line here, not a new component.
 */
export function BannerBridge() {
  const { raise, resolve } = useBanner();
  const {
    sidecarReachable,
    dismissedSidecarNotice,
    llmHealth,
  } = useStudio();
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
    // The offline strip is the one line while the browser has no network: this
    // strip's Recheck and Start-the-sidecar actions could not succeed anyway.
    if (sidecarReachable === false && !dismissedSidecarNotice && online) {
      raise({ kind: "sidecar-down" });
    } else {
      resolve("sidecar-down");
    }
  }, [sidecarReachable, dismissedSidecarNotice, online, raise, resolve]);

  useEffect(() => {
    // Same reason as the sidecar strip: the offline line says what still works.
    if (llmHealth.healthy === false && online) {
      raise({ kind: "model-offline" });
    } else {
      resolve("model-offline");
    }
  }, [llmHealth.healthy, online, raise, resolve]);

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
  const {
    recheckConnections,
    openSetup,
    openPanel,
    dismissSidecarNotice,
    ask,
  } = useStudio();

  function onAction(action: BannerActionId) {
    switch (action) {
      case "recheck-sidecar":
        void recheckConnections();
        break;
      case "open-setup":
        openSetup();
        break;
      case "open-capture":
        openPanel("capture");
        break;
      case "open-jobmap":
        openPanel("jobmap");
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
