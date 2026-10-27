import { useEffect } from "react";

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

  useEffect(() => {
    if (sidecarReachable === false && !dismissedSidecarNotice) {
      raise({ kind: "sidecar-down" });
    } else {
      resolve("sidecar-down");
    }
  }, [sidecarReachable, dismissedSidecarNotice, raise, resolve]);

  useEffect(() => {
    if (llmHealth.healthy === false) {
      raise({ kind: "model-offline" });
    } else {
      resolve("model-offline");
    }
  }, [llmHealth.healthy, raise, resolve]);

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
