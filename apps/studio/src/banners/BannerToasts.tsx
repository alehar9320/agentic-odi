import { useEffect, useRef } from "react";

import { announce } from "../lib/announce";
import { useToasts } from "../state/notices/NoticesContext";
import { useBanner } from "./BannerProvider";
import type { BannerKind } from "./types";

const TOAST_KIND: Record<string, BannerKind> = {
  success: "success",
  error: "error",
  info: "info",
};

/**
 * The last mile between the studio's existing `pushToast` calls and the banner
 * system.
 *
 * Every toast the studio raises becomes a banner, keyed by the toast id, so the
 * two cannot drift and no call site has to change. Only toasts that actually
 * left are cleared, so a new toast does not restart the animation of the ones
 * already on screen.
 *
 * Reads only the toast list from `NoticesContext`, so a settings or theme
 * change elsewhere never re-renders this component.
 */
export function BannerToasts() {
  const toasts = useToasts();
  const { raise, dismiss } = useBanner();
  const shown = useRef<Set<string>>(new Set());

  useEffect(() => {
    const live = new Set(toasts.map((toast) => `toast-${toast.id}`));
    for (const key of shown.current) {
      if (!live.has(key)) {
        dismiss(key);
      }
    }
    for (const toast of toasts) {
      raise({
        kind: TOAST_KIND[toast.kind] ?? "info",
        key: `toast-${toast.id}`,
        body: toast.message,
        ...(toast.durationMs ? { durationMs: toast.durationMs } : {}),
        ...(toast.action
          ? { actions: [{ label: toast.action.label, run: toast.action.run, tone: "ghost" as const }] }
          : {}),
      });
      // The banner is the visual; the sentence is spoken once, by the single
      // Announcer region, so a burst of toasts is a burst of sentences in
      // order rather than several live regions talking over one another.
      if (!shown.current.has(`toast-${toast.id}`)) {
        announce(toast.message);
      }
    }
    shown.current = live;
  }, [toasts, raise, dismiss]);

  return null;
}
