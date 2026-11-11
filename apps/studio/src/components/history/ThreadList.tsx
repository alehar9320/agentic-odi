/**
 * The conversation history list, composed from assistant-ui thread-list
 * primitives over the external-store adapter wired in StudioRuntime.
 *
 * One tab stop per row (the trigger). Enter/Space switches threads; arrow
 * keys move between the trigger and the overflow menu. The current row carries
 * `aria-current`. Escape closes the list and returns focus to the bar button —
 * that is handled by StudioBar's history-open state, not here.
 */

import { useAui } from "@assistant-ui/store";
import { useAuiState } from "@assistant-ui/store";
import {
  ThreadListItemMorePrimitive,
  ThreadListItemPrimitive,
  ThreadListPrimitive,
} from "@assistant-ui/react";

import { formatRelativeTime } from "../../lib/relativeTime";

/** One row of the history list: switch trigger plus overflow actions. */
function ThreadListItemRow() {
  const aui = useAui();
  const threadListItem = useAuiState((s) => s.threadListItem);
  const { id, title, custom } = threadListItem;
  const updatedAt =
    typeof custom?.updatedAt === "string" ? (custom.updatedAt as string) : undefined;

  return (
    <ThreadListItemPrimitive.Root key={id}>
      <ThreadListItemPrimitive.Trigger>
        <ThreadListItemPrimitive.Title fallback="New conversation" />
        {updatedAt && (
          <span className="history__meta">{formatRelativeTime(updatedAt)}</span>
        )}
      </ThreadListItemPrimitive.Trigger>
      <ThreadListItemMorePrimitive.Root sharedFocusGroup>
        <ThreadListItemMorePrimitive.Trigger>
          <span className="sr-only">
            More actions for {title ?? "this conversation"}
          </span>
        </ThreadListItemMorePrimitive.Trigger>
        <ThreadListItemMorePrimitive.Content>
          <ThreadListItemMorePrimitive.Item
            onSelect={() => {
              const next = prompt("Rename this conversation:", title ?? "");
              if (next !== null) {
                aui.threads.item({ id }).rename(next);
              }
            }}
          >
            Rename
          </ThreadListItemMorePrimitive.Item>
          <ThreadListItemMorePrimitive.Item
            onSelect={() => {
              if (
                window.confirm("Delete this conversation and all its turns?")
              ) {
                aui.threads.item({ id }).delete();
              }
            }}
          >
            Delete
          </ThreadListItemMorePrimitive.Item>
        </ThreadListItemMorePrimitive.Content>
      </ThreadListItemMorePrimitive.Root>
      <ThreadListItemPrimitive.Delete />
    </ThreadListItemPrimitive.Root>
  );
}

export function ThreadList() {
  return (
    <ThreadListPrimitive.Root>
      <ThreadListPrimitive.New />
      <ThreadListPrimitive.Items>
        {(value) => {
          const { id } = value.threadListItem;
          return <ThreadListItemRow key={id} />;
        }}
      </ThreadListPrimitive.Items>
    </ThreadListPrimitive.Root>
  );
}
