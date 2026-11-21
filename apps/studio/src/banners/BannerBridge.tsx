import { useEffect } from "react";

import { useOnlineStatus } from "../lib/onlineStatus";
import { dismissAppUpdate, reloadForUpdate, useAppUpdate } from "../lib/swUpdate";
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
    llmHealth,
    streaming,
  } = useStudio();
  const online = useOnlineStatus();
  const appUpdate = useAppUpdate();

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
    // A staged build is offered once, and never mid-sentence: while a turn is
    // streaming the offer waits, so activating the new worker cannot reload the
    // page under a reply that is still arriving.
    if (appUpdate.ready && !appUpdate.dismissed && !streaming) {
      raise({ kind: "app-update-ready" });
    } else {
      resolve("app-update-ready");
    }
  }, [appUpdate.ready, appUpdate.dismissed, streaming, raise, resolve]);

  useEffect(() => {
    // The offline strip is the one line while the browser has no network.
    if (!online) {
      raise({ kind: "offline" });
    } else {
      resolve("offline");
    }
  }, [online, raise, resolve]);

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
      case "reload-app":
        // Take the waiting worker and reload into the new build. This is the one
        // place an update activates, and only from a person's click.
        reloadForUpdate();
        break;
    }
  }

function onDismiss(id: string) {
    // The update offer is once per page: dismissing it must not bring it back on
    // the next render, and it must never loop.
    if (id === "app-update-ready") {
      dismissAppUpdate();
    }
    dismiss(id);
  }

  return { onIntent: ask, onAction, onDismiss };
}
