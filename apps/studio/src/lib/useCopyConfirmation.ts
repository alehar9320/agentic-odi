import { useCallback, useEffect, useRef, useState } from "react";

/**
 * How long a "Copied" confirmation holds before the control reads "Copy" again.
 *
 * Short enough that a second copy re-triggers it without waiting, long enough
 * that the tick is seen. Shared by every copy control so the confirmation does
 * not time out at a different pace in two places.
 */
export const COPY_CONFIRMATION_MS = 1600;

/**
 * Copy text and confirm it in place for `COPY_CONFIRMATION_MS`.
 *
 * Returns `copied` for the control to read and a `copy` that resolves to
 * whether the clipboard accepted the write, so a caller can say so when it did
 * not. A second copy restarts the confirmation rather than stacking timers.
 */
export function useCopyConfirmation(): {
  copied: boolean;
  copy: (text: string) => Promise<boolean>;
} {
  const [copied, setCopied] = useState(false);
  const timer = useRef<number | null>(null);

  useEffect(
    () => () => {
      if (timer.current !== null) {
        window.clearTimeout(timer.current);
      }
    },
    [],
  );

  const copy = useCallback(async (text: string) => {
    if (!navigator.clipboard) {
      return false;
    }
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      return false;
    }
    setCopied(true);
    if (timer.current !== null) {
      window.clearTimeout(timer.current);
    }
    timer.current = window.setTimeout(() => setCopied(false), COPY_CONFIRMATION_MS);
    return true;
  }, []);

  return { copied, copy };
}
