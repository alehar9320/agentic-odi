/**
 * The conversation list, in the shape assistant-ui's thread list renders.
 *
 * The external store exposes a thread-list adapter but a thread row carries no
 * timestamps, so the date and the turn count travel in `custom`. This module is
 * a pure mapping: the Studio context owns the conversations and the switching,
 * and this only renames them into the library's types. The adapter is marked
 * experimental upstream, which is why it lives alone here — an upgrade touches
 * this file and nothing else.
 */

import type {
  ExternalStoreThreadData,
  ExternalStoreThreadListAdapter,
} from "@assistant-ui/react";

import type { Conversation } from "../types";

/** What a conversation with no title yet is called, in the list and the row. */
export const UNTITLED_CONVERSATION = "New conversation";

/** One stored conversation as a thread list row. */
export function toThreadListItem(
  conversation: Conversation,
): ExternalStoreThreadData<"regular"> {
  const title = (conversation.title ?? "").trim();
  return {
    status: "regular",
    id: conversation.id,
    title: title || UNTITLED_CONVERSATION,
    custom: {
      updatedAt: conversation.updated_at,
      turnCount: conversation.turn_count ?? 0,
    },
  };
}

export interface ThreadListSource {
  conversations: Conversation[];
  /** The conversation on stage, so the list marks it. */
  conversationId: string | null;
  loading?: boolean;
  onSwitchToThread: (conversationId: string) => void | Promise<void>;
  onSwitchToNewThread: () => void | Promise<void>;
}

/** The runtime adapter the drawer's thread list reads. */
export function threadListAdapter(
  source: ThreadListSource,
): ExternalStoreThreadListAdapter {
  return {
    threadId: source.conversationId ?? undefined,
    isLoading: source.loading ?? false,
    // A list that has not loaded (or a surface that only stubs the store) is
    // empty, not a crash: the drawer shows its empty state instead.
    threads: (source.conversations ?? []).map(toThreadListItem),
    onSwitchToThread: (threadId) => source.onSwitchToThread(threadId),
    onSwitchToNewThread: () => source.onSwitchToNewThread(),
  };
}
