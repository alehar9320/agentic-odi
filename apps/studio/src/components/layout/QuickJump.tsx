import { useEffect, useId, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { createPortal } from "react-dom";

import { matchCommands, type StudioCommand } from "../../lib/commands";
import { useFocusTrap } from "../../lib/useFocusTrap";
import { useStudio } from "../../state/StudioContext";

interface JumpRow {
  key: string;
  label: string;
  hint: string;
  run: () => void;
}

/**
 * Quick jump (#736): the one meaning of Meta/Ctrl+K.
 *
 * The first row is New inquiry, which hands the caret back to the composer.
 * The rest are the recent threads and the same commands the slash palette
 * runs, so there is one vocabulary and one implementation. It is a modal: a
 * dialog owns Escape, focus stays inside, and the shell behind it is inert.
 */
export function QuickJump({
  open,
  onClose,
  onNewInquiry,
  onCommand,
}: {
  open: boolean;
  onClose: () => void;
  /** Close the sheet and put the caret in the composer. */
  onNewInquiry: () => void;
  onCommand: (command: StudioCommand) => void;
}) {
  const {
    conversations,
    conversationId,
    openConversation,
    refreshConversations,
    pushToast,
  } = useStudio();
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const dialogRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const id = useId();

  useFocusTrap(dialogRef, open, true);

  // The list is read when it opens, like the bar's history menu. The sheet is
  // mounted only while open, so its query and highlight start fresh each time.
  useEffect(() => {
    if (open) {
      void refreshConversations();
    }
  }, [open, refreshConversations]);

  const rows = useMemo<JumpRow[]>(() => {
    if (!open) {
      return [];
    }
    const needle = query.trim().toLowerCase();
    const list: JumpRow[] = [];
    if (!needle || "new inquiry".includes(needle)) {
      list.push({
        key: "new",
        label: "New inquiry",
        hint: "Start a new thread and put the caret in the composer",
        run: onNewInquiry,
      });
    }

    let threads = 0;
    for (const conversation of conversations ?? []) {
      const title = conversation.title.trim() || "New conversation";
      if (needle && !title.toLowerCase().includes(needle)) {
        continue;
      }
      list.push({
        key: `thread-${conversation.id}`,
        label: title,
        hint:
          conversation.id === conversationId
            ? "The thread on the mainstage"
            : "Open this thread",
        run: () => {
          onClose();
          void openConversation(conversation.id).catch(() =>
            pushToast("error", "I couldn't open that conversation."),
          );
        },
      });
      threads += 1;
      if (threads >= 6) {
        break;
      }
    }

    for (const command of matchCommands(needle ? `/${needle}` : "/")) {
      list.push({
        key: `command-${command.id}`,
        label: `${command.name} — ${command.label}`,
        hint: command.description,
        run: () => {
          onClose();
          onCommand(command);
        },
      });
    }
    return list;
  }, [
    conversationId,
    conversations,
    onClose,
    onCommand,
    onNewInquiry,
    open,
    openConversation,
    pushToast,
    query,
  ]);

  if (!open) {
    return null;
  }

  // A shorter result list never leaves the highlight stranded past its end.
  const selected = Math.min(active, Math.max(rows.length - 1, 0));

  function onFieldKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActive(rows.length ? (selected + 1) % rows.length : 0);
      return;
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive(rows.length ? (selected - 1 + rows.length) % rows.length : 0);
      return;
    }
    if (event.key === "Enter") {
      event.preventDefault();
      rows[selected]?.run();
    }
  }

  function onDialogKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key !== "Escape") {
      return;
    }
    // The dialog owns its Escape; the stream behind it keeps running.
    event.preventDefault();
    event.stopPropagation();
    onClose();
  }

  return createPortal(
    <div className="quickjump-overlay fade-in">
      <button
        type="button"
        className="quickjump__scrim"
        aria-label="Close quick jump"
        onClick={onClose}
      />
      <div
        ref={dialogRef}
        className="quickjump"
        role="dialog"
        aria-modal="true"
        aria-label="Quick jump"
        onKeyDown={onDialogKeyDown}
      >
        <input
          ref={inputRef}
          className="quickjump__field"
          type="search"
          role="combobox"
          aria-expanded="true"
          aria-autocomplete="list"
          aria-controls={`${id}-list`}
          aria-label="Search threads and commands"
          placeholder="Jump to a thread or a command"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={onFieldKeyDown}
          autoFocus
        />
        <div
          className="quickjump__list"
          id={`${id}-list`}
          role="listbox"
          aria-label="Quick jump results"
        >
          {rows.length === 0 ? (
            <p className="quickjump__empty" role="status">
              No thread or command matches “{query.trim()}”.
            </p>
          ) : (
            rows.map((row, index) => (
              <button
                key={row.key}
                type="button"
                role="option"
                aria-selected={index === selected}
                className={`quickjump__row${index === selected ? " is-active" : ""}`}
                onMouseEnter={() => setActive(index)}
                onClick={row.run}
              >
                <span className="quickjump__label">{row.label}</span>
                <span className="quickjump__hint">{row.hint}</span>
              </button>
            ))
          )}
        </div>
        <p className="quickjump__foot">
          <kbd>↑</kbd>
          <kbd>↓</kbd> to move · <kbd>Enter</kbd> to open · <kbd>Esc</kbd> to close
        </p>
      </div>
    </div>,
    document.body,
  );
}
