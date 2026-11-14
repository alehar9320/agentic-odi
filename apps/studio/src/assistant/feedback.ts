/**
 * The adapter between assistant-ui's feedback contract and the Studio's local
 * store.
 *
 * assistant-ui emits a verdict on a reply through a `FeedbackAdapter`; the
 * Studio keeps it in its own local store so the team learns which answers
 * helped. The adapter maps one reply's stable message id and its conversation
 * onto the feedback endpoints. A rejected submit is reported quietly and never
 * rolls the reply back: a rating is a note about the reply, not part of it.
 */

import type { FeedbackAdapter, ThreadMessage } from "@assistant-ui/react";

import { listFeedback, recordFeedback } from "../api/studioApi";
import type { MessageFeedback } from "../types";

export interface FeedbackDeps {
  /** The thread the rated reply belongs to, or null before one exists. */
  conversationId: () => string | null;
  /** One quiet notice when a submit is refused. */
  onError?: (message: string) => void;
}

/**
 * The real adapter. assistant-ui calls `submit` with the message and verdict;
 * the write is fire-and-forget because the contract returns nothing, and a
 * failure surfaces as one notice rather than an unhandled rejection.
 */
export function createFeedbackAdapter(deps: FeedbackDeps): FeedbackAdapter {
  return {
    submit: (feedback: { message: ThreadMessage; type: "positive" | "negative"; comment?: string }) => {
      const conversationId = deps.conversationId();
      if (!conversationId) {
        return;
      }
      void recordFeedback({
        conversation_id: conversationId,
        message_id: feedback.message.id,
        type: feedback.type,
        comment: feedback.comment ?? null,
      }).catch(() => {
        deps.onError?.("The rating could not be saved on this device.");
      });
    },
  };
}

/** The stored verdicts for one conversation, so a reload restores them. */
export async function loadFeedback(conversationId: string): Promise<MessageFeedback[]> {
  try {
    return await listFeedback(conversationId);
  } catch {
    return [];
  }
}
