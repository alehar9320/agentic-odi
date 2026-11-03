import { useEffect, useState } from "react";

import { useStudio } from "../state/StudioContext";
import { edgeManager, hasModelEndpoint } from "../edge/manager";
import { formatGB, tierById } from "../edge/ladder";
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
    settings,
  } = useStudio();
  // Bumped whenever something changes what the browser could do with a model:
  // an answered consent question, or a tier that just landed. Download
  // progress deliberately does not bump it — that would re-run this whole
  // decision dozens of times per second to reach the same conclusion.
  const [edgeRevision, setEdgeRevision] = useState(0);

  useEffect(() => {
    if (sidecarReachable === false && !dismissedSidecarNotice) {
      raise({ kind: "sidecar-down" });
    } else {
      resolve("sidecar-down");
    }
  }, [sidecarReachable, dismissedSidecarNotice, raise, resolve]);

  useEffect(() => {
    // Three states, and only one strip at a time: the browser is already
    // answering, it could answer if the person said yes, or it can't.
    //
    // The question to ask is *"is anything answering for this studio?"* — not
    // "did a probe fail?". A browser-only visitor has no server to probe, and
    // main's survey deliberately refuses to record a refusal it did not witness
    // (#309: no apology on a first run that needed nothing). Waiting for
    // `healthy === false` here would mean the offer is only ever shown to
    // someone who had a model and lost it — never to the person this feature
    // exists for. So an endpoint that is configured, or that is answering,
    // settles it; an unmeasured nothing is still a nothing.
    if (llmHealth.healthy === true || hasModelEndpoint(settings)) {
      if (llmHealth.healthy === false) {
        raise({ kind: "model-offline" });
      } else {
        resolve("model-offline");
      }
      resolve("edge-offer");
      return;
    }
    let cancelled = false;
    void (async () => {
      // Past the guard above nothing is answering for this studio — measured
      // down, or never measurable. A strip is not something a person typed
      // into: read storage and decide after, instead of answering from what
      // this tab last knew.
      await edgeManager.sync();
      const serving = edgeManager.canServe(settings, false);
      const offer = serving ? null : await edgeManager.offerFor(settings, false);
      if (cancelled) {
        return;
      }
      if (serving) {
        resolve("model-offline");
        resolve("edge-offer");
      } else if (offer) {
        resolve("model-offline");
        raise({
          kind: "edge-offer",
          body: `No model key, nothing sent to anyone else. ${offer.label} is about ${formatGB(offer.approxBytes)}, once — then your replies run in this tab.`,
        });
      } else {
        resolve("edge-offer");
        if (edgeManager.isBusy()) {
          // Consent just arrived and the fetch is under way; the download
          // strip tells that story better than "no model is reachable".
          resolve("model-offline");
        } else if (llmHealth.healthy === false) {
          // A measured refusal. An unmeasured one is a browser with nothing to
          // measure, and saying "no model is reachable" about it would blame
          // the person's studio for a thing they never asked it to be.
          raise({ kind: "model-offline" });
        } else {
          resolve("model-offline");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [llmHealth.healthy, settings, edgeRevision, raise, resolve]);

  useEffect(() => {
    const unsubscribe = edgeManager.addNoticeListener((notice) => {
      if (notice.kind === "downloading") {
        const percent = Math.round(notice.progress.percent * 100);
        raise({
          kind: "edge-downloading",
          body: `Fetching ${tierById(notice.tier).label} (${percent}%) — this browser's next voice.`,
        });
        return;
      }
      resolve("edge-downloading");
      if (notice.kind === "ready") {
        raise({
          kind: "edge-ready",
          body: `${tierById(notice.tier).label} is answering in this tab now — free.`,
        });
      } else if (notice.kind === "unlocked") {
        raise({
          kind: "edge-unlocked",
          body: `${tierById(notice.tier).label} is answering in this browser now — free.`,
        });
      }
      setEdgeRevision((revision) => revision + 1);
    });
    return unsubscribe;
  }, [raise, resolve]);

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
  const { raise, dismiss } = useBanner();
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
      case "enable-edge-model":
        void edgeManager.grantAndStart().then(async (tier) => {
          if (tier !== null) {
            return;
          }
          // Nothing started here. Another tab may already be fetching it —
          // in which case the model is arriving and a complaint would be a
          // lie — or the moment was genuinely wrong.
          if ((await edgeManager.servedTier()) === null) {
            raise({
              kind: "error",
              body: "That download didn't start here. Another tab may be fetching it, or this browser is waiting for a visible, idle moment off a Save Data connection.",
            });
          }
        });
        break;
      case "decline-edge-model":
        // Durable: the studio asks once, and Settings is where the answer
        // can change. The consent notice re-runs the strip decision.
        void edgeManager.decline();
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
