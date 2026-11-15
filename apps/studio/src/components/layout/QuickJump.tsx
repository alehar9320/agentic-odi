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
 * The first row is New inquiry, which hands the caret back to the composer
 * without discarding the thread on screen. The rest are the recent threads and
 * the same commands the slash palette runs, so there is one vocabulary and one
 * implementation. It is a modal: a dialog owns Escape, focus stays inside, and
 * the shell behind it is inert.
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
    closeCustomize,
  } = useStudio();
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const dialogRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
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
        hint: "Put the caret in the composer for a new inquiry",
        run: () => {
          onClose();
          // Customize replaces the conversation; leaving it first makes the
          // composer exist by the time focus is handed back.
          closeCustomize();
          onNewInquiry();
        },
      });
    }

    let threads = 0;
    for (const conversation of conversations ?? []) {
      const title = conversation.title.trim() || "New conversation";
      if (needle && !title.toLowerCase().includes(needle)) {
        continue;
      }
      const current = conversation.id === conversationId;
      list.push({
        key: `thread-${conversation.id}`,
        label: title,
        hint: current ? "The thread on the mainstage" : "Open this thread",
        run: () => {
          onClose();
          closeCustomize();
          // Reopening the thread already on screen would abort its reply and
          // reload the saved turns. Choosing it means "stay here".
          if (current) {
            return;
          }
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

    // matchCommands accepts text with or without the slash, so a typed
    // `/help` is not turned into `//help`.
    for (const command of matchCommands(needle || "/")) {
      list.push({
        key: `command-${command.id}`,
        label: `${command.name} — ${command.label}`,
        hint: command.description,
        run: () => {
          onClose();
          closeCustomize();
          onCommand(command);
        },
      });
    }
    return list;
  }, [
    closeCustomize,
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

  // A shorter result list never leaves the highlight stranded past its end.
  const selected = Math.min(active, Math.max(rows.length - 1, 0));

  // Keep the active row on screen; the list can be taller than the sheet.
  useEffect(() => {
    const row = listRef.current?.querySelector<HTMLElement>('[aria-selected="true"]');
    row?.scrollIntoView?.({ block: "nearest" });
  }, [selected, query]);

  if (!open) {
    return null;
  }

  function onFieldKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    // An input method owns these keys while it is composing: Enter chooses a
    // candidate, it does not run the highlighted row.
    if (event.nativeEvent.isComposing) {
      return;
    }
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
    if (event.key !== "Escape" || event.nativeEvent.isComposing) {
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
          aria-activedescendant={rows.length ? `${id}-row-${selected}` : undefined}
          aria-label="Search threads and commands"
          placeholder="Jump to a thread or a command"
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            setActive(0);
          }}
          onKeyDown={onFieldKeyDown}
          autoFocus
        />
        <div
          ref={listRef}
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
                id={`${id}-row-${index}`}
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
