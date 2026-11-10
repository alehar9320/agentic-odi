/**
 * A Studio conversation list as assistant-ui thread-list data.
 *
 * Pure: no store, no sidecar, no rendering. Orders newest first, names an
 * untitled thread, and parks `updated_at` in `custom` since
 * `ExternalStoreThreadData` carries no timestamp field.
 */

import type { ConversationSummary } from "../types";
import type { ExternalStoreThreadData } from "@assistant-ui/react";

/** A blank title reads as "New conversation", matching the hand-built menu. */
const UNTITLED = "New conversation";

export function toThreadData(
  conversations: ConversationSummary[],
): ExternalStoreThreadData<"regular">[] {
  return [...conversations]
    .sort((a, b) => (b.updated_at ?? "").localeCompare(a.updated_at ?? ""))
    .map((conversation) => ({
      id: conversation.id,
      title: conversation.title.trim() || UNTITLED,
      status: "regular",
      custom: {
        updatedAt: conversation.updated_at,
      },
    }));
}
