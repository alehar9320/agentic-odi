/**
 * Conversation history.
 *
 * The sidecar remembers every thread; this is the assistant-ui thread list over
 * it. Switching, renaming, and deleting all go through the runtime's thread-list
 * adapter (`assistant/StudioRuntime.tsx`), so the sidebar never talks to the API
 * itself and the runtime stays the one place that knows how a thread changes.
 */

import { ThreadListItemPrimitive, ThreadListPrimitive, useAui, useAuiState } from "@assistant-ui/react";
import { useState } from "react";

import { useMediaQuery } from "../../lib/useMediaQuery";
import { useStudio } from "../../state/StudioContext";
import { CloseIcon, HistoryIcon, PencilIcon, PlusIcon } from "../icons";

/**
 * One row: the thread's title, with rename and forget beside it.
 *
 * Renaming stays in the row rather than in a dialog: the title is the thing
 * being changed, so the field appears where it was read. Escape leaves the old
 * title alone; Enter or leaving the field saves it.
 */
function HistoryRow({ onNavigate }: { onNavigate: () => void }) {
  const aui = useAui();
  const title = useAuiState((state) => state.threadListItem.title) ?? "";
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");

  function startEditing() {
    setDraft(title);
    setEditing(true);
  }

  function commit() {
    const next = draft.trim();
    setEditing(false);
    if (next && next !== title) {
      aui.threadListItem().rename(next);
    }
  }

  const label = title || "Untitled thread";

  return (
    <ThreadListItemPrimitive.Root className="history__item">
      {editing ? (
        <div className="history__rename">
          <input
            className="history__rename-input"
            aria-label="Conversation title"
            value={draft}
            autoFocus
            onChange={(event) => setDraft(event.target.value)}
            onBlur={commit}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                commit();
              }
              if (event.key === "Escape") {
                event.preventDefault();
                setEditing(false);
              }
            }}
          />
        </div>
      ) : (
        <>
          <ThreadListItemPrimitive.Trigger className="history__trigger" onClick={onNavigate}>
            <ThreadListItemPrimitive.Title fallback="Untitled thread" />
          </ThreadListItemPrimitive.Trigger>
          <button
            type="button"
            className="history__action"
            aria-label={`Rename ${label}`}
            title="Rename conversation"
            onClick={startEditing}
          >
            <PencilIcon size={12} />
          </button>
          <ThreadListItemPrimitive.Delete
            className="history__delete"
            aria-label={`Delete ${label}`}
            title="Delete conversation"
          >
            <CloseIcon size={13} />
          </ThreadListItemPrimitive.Delete>
        </>
      )}
    </ThreadListItemPrimitive.Root>
  );
}

export function HistorySidebar({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const { conversationsLoading } = useStudio();
  // On a narrow screen the list covers the thread, so opening a thread has to
  // put it away again. On a wide screen it stays out of the reader's way.
  const isMobile = useMediaQuery("(max-width: 1023px)");

  if (!open) {
    return null;
  }

  function navigate() {
    if (isMobile) {
      onClose();
    }
  }

  return (
    <aside className="history" aria-label="Conversation history">
      <header className="history__head">
        <div className="history__heading">
          <HistoryIcon size={15} />
          <h2 className="history__title">Conversations</h2>
        </div>
        <button
          type="button"
          className="icon-button"
          aria-label="Close conversation history"
          onClick={onClose}
        >
          <CloseIcon size={15} />
        </button>
      </header>

      <ThreadListPrimitive.Root className="history__list">
        <ThreadListPrimitive.New className="history__new" onClick={navigate}>
          <PlusIcon size={14} />
          New conversation
        </ThreadListPrimitive.New>

        <ThreadListPrimitive.Items>
          {() => <HistoryRow onNavigate={navigate} />}
        </ThreadListPrimitive.Items>
      </ThreadListPrimitive.Root>

      {conversationsLoading ? (
        <p className="history__status" role="status">
          Loading conversations…
        </p>
      ) : null}
    </aside>
  );
}
