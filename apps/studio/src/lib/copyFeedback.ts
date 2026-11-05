/**
 * Copying says the same thing, in the same voice, for the same 1600 ms.
 *
 * Three surfaces copy — a reply, a fenced block, a failure — so the timer and
 * the one polite live region live here instead of in each of them. D47 will
 * fold this into the studio-wide announcer; until then this is the only voice
 * a copy has, and a burst of copies is still one sentence at a time.
 */

import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";

/** How long a control says "Copied" before it says what it does again. */
export const COPIED_MS = 1600;

/** Write `text` to the clipboard. False when the browser refused or has none. */
export async function copyText(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    return false;
  }
  return false;
}

let announcement = "";
const listeners = new Set<() => void>();

/** Say one short sentence in the studio's single polite live region. */
export function announce(text: string): void {
  announcement = text;
  for (const listener of listeners) {
    listener();
  }
}

export function useAnnouncement(): string {
  return useSyncExternalStore(
    (onChange) => {
      listeners.add(onChange);
      return () => listeners.delete(onChange);
    },
    () => announcement,
    () => "",
  );
}

/**
 * True for `ms` after each `confirm()`. A second copy restarts the window
 * rather than leaving the first one to expire under it.
 */
export function useCopyFeedback(ms: number = COPIED_MS): {
  copied: boolean;
  confirm: () => void;
} {
  const [copied, setCopied] = useState(false);
  const timer = useRef<number | null>(null);

  const clear = useCallback(() => {
    if (timer.current !== null) {
      window.clearTimeout(timer.current);
      timer.current = null;
    }
  }, []);

  useEffect(() => clear, [clear]);

  const confirm = useCallback(() => {
    clear();
    setCopied(true);
    timer.current = window.setTimeout(() => {
      timer.current = null;
      setCopied(false);
    }, ms);
  }, [clear, ms]);

  return { copied, confirm };
}
