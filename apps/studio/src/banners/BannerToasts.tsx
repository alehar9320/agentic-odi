import { useEffect, useRef } from "react";

import { useStudio } from "../state/StudioContext";
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
 */
export function BannerToasts() {
  const { toasts } = useStudio();
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
      });
    }
    shown.current = live;
  }, [toasts, raise, dismiss]);

  return null;
}
