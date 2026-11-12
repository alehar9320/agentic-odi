/**
 * Composer history recall.
 *
 * `unstable_useComposerInputHistory` is experimental, so it is wrapped here:
 * the studio never imports the unstable name directly, and an upgrade is one
 * edit. Verified against `@assistant-ui/react@0.15.31`.
 *
 * The hook reads the thread's own user messages — the same ones
 * `convertMessage` produces — so there is exactly one history. Nothing is
 * persisted, and the edit composer is untouched by design.
 */

import { unstable_useComposerInputHistory } from "@assistant-ui/react";

export type ComposerHistory = ReturnType<typeof unstable_useComposerInputHistory>;

export function useComposerHistory(): ComposerHistory {
  return unstable_useComposerInputHistory();
}

/** The sentence a screen reader hears after a recall, in one short line. */
export function recallAnnouncement(text: string): string {
  const flat = text.replace(/\s+/g, " ").trim();
  const short = flat.length > 80 ? `${flat.slice(0, 79).trimEnd()}…` : flat;
  return `Recalled your last message: ${short}`;
}
