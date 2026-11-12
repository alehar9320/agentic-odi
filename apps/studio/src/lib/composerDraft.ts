/**
 * An unsent message survives a reload.
 *
 * A draft is kept per conversation, so reopening a thread restores what was
 * being typed and starting a new one does not inherit it. The store is the
 * browser's own, so a sidecar that is down cannot lose the draft; a storage
 * that refuses (private mode, quota) fails soft and the composer still works.
 */

const DRAFT_PREFIX = "studio.draft.";

/** The slot a draft lives in. A brand-new thread has no id yet. */
function draftKey(conversationId: string | null): string {
  return `${DRAFT_PREFIX}${conversationId ?? "new"}`;
}

/** The stored draft for a conversation, or "" when there is none. */
export function loadDraft(conversationId: string | null): string {
  try {
    return localStorage.getItem(draftKey(conversationId)) ?? "";
  } catch {
    return "";
  }
}

/**
 * Remember the draft, or clear it when the text is empty.
 *
 * An empty draft removes the key rather than storing "" so a sent message
 * leaves nothing behind for the next open to restore.
 */
export function saveDraft(conversationId: string | null, text: string): void {
  try {
    if (text === "") {
      localStorage.removeItem(draftKey(conversationId));
      return;
    }
    localStorage.setItem(draftKey(conversationId), text);
  } catch {
    /* storage unavailable: the draft lives only in memory this session */
  }
}

/** Drop a conversation's draft; used when its message is sent. */
export function clearDraft(conversationId: string | null): void {
  saveDraft(conversationId, "");
}
