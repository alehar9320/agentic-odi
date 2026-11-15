import { useEffect, useRef } from "react";

import { useToasts } from "../state/notices/NoticesContext";
import { noticeFromBanner } from "../notices/fromBanner";
import { useActivityOptional } from "../notices/ActivityProvider";
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
  const activity = useActivityOptional();
  const record = activity?.record;
  const shown = useRef<Set<string>>(new Set());
  // Only toasts this component has not already recorded are written down, so a
  // re-render that re-raises an existing toast does not add a second notice.
  const recorded = useRef<Set<number>>(new Set());

  useEffect(() => {
    const live = new Set(toasts.map((toast) => `toast-${toast.id}`));
    for (const key of shown.current) {
      if (!live.has(key)) {
        dismiss(key);
      }
    }
    for (const toast of toasts) {
      const kind = TOAST_KIND[toast.kind] ?? "info";
      const spec = {
        kind,
        key: `toast-${toast.id}`,
        body: toast.message,
        ...(toast.durationMs ? { durationMs: toast.durationMs } : {}),
        ...(toast.action
          ? { actions: [{ label: toast.action.label, run: toast.action.run, tone: "ghost" as const }] }
          : {}),
      };
      raise(spec);
      // A toast is the shortest-lived notice of all: recording it here is what
      // keeps "Added connector X" readable after its six seconds are up.
      if (record && !recorded.current.has(toast.id)) {
        recorded.current.add(toast.id);
        record(noticeFromBanner(spec));
      }
    }
    shown.current = live;
  }, [toasts, raise, dismiss, record]);

  return null;
}
