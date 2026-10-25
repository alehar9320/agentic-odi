import { useEffect, useMemo, useRef, useState, type RefObject } from "react";

import { MAX_ATTACHMENTS, formatBytes, isImage, type StagedAttachment } from "../../lib/attachments";
import { isCommandDraft, matchCommands, type StudioCommand } from "../../lib/commands";
import { useStudio } from "../../state/StudioContext";
import { ArrowUpIcon, FileIcon, PaperclipIcon, StopIcon } from "../icons";
import { ModelPicker } from "./ModelPicker";

interface ComposerProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: (text?: string) => void;
  onCommand: (command: StudioCommand) => void;
  streaming: boolean;
  onStop: () => void;
  inputRef: RefObject<HTMLTextAreaElement | null>;
  autoFocus?: boolean;
  /** Overrides the default placeholder, e.g. while setting up context. */
  placeholder?: string;
  /** Files waiting to be sent. Omitted where attaching makes no sense. */
  attachments?: StagedAttachment[];
  onAttachFiles?: (files: File[]) => void;
  onRemoveAttachment?: (id: string) => void;
  /** Why the last file was refused, in words the reader can act on. */
  attachmentError?: string | null;
}

const MAX_HEIGHT = 220;
const HINT_ID = "studio-composer-hint";
const FILES_ID = "studio-composer-files";

/** Stable element id for the highlighted slash-command option. */
function optionId(command: StudioCommand): string {
  return `studio-command-${command.id}`;
}

export function Composer({
  value,
  onChange,
  onSubmit,
  onCommand,
  streaming,
  onStop,
  inputRef,
  autoFocus = false,
  placeholder,
  attachments = [],
  onAttachFiles,
  onRemoveAttachment,
  attachmentError = null,
}: ComposerProps) {
  const { llmHealth, brief, connectorSuggestions, presets, dismissConnectorSuggestion, refreshConnectors } =
    useStudio();
  const [highlight, setHighlight] = useState(0);
  // Remember which draft was dismissed, so typing again re-opens the palette
  // without an effect that writes state on every keystroke.
  const [dismissedFor, setDismissedFor] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  const offline = llmHealth.healthy === false;
  const matches = useMemo(() => (isCommandDraft(value) ? matchCommands(value) : []), [value]);
  const paletteOpen = isCommandDraft(value) && dismissedFor !== value;
  const canAttach = Boolean(onAttachFiles) && attachments.length < MAX_ATTACHMENTS;

  // Grow with the draft, then scroll once it gets tall.
  useEffect(() => {
    const element = inputRef.current;
    if (!element) {
      return;
    }
    element.style.height = "auto";
    element.style.height = `${Math.min(element.scrollHeight, MAX_HEIGHT)}px`;
  }, [value, inputRef]);

  useEffect(() => {
    if (!autoFocus) {
      return;
    }
    inputRef.current?.focus();
  }, [autoFocus, inputRef]);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        inputRef.current?.focus();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [inputRef]);

  // A file is a contribution on its own: a screenshot with no sentence is still
  // a question the reader wants answered.
  const canSend = (value.trim().length > 0 || attachments.length > 0) && !streaming;
  const activeIndex = Math.min(highlight, Math.max(matches.length - 1, 0));
  const activeCommand = matches[activeIndex];

  function choose(command: StudioCommand) {
    onChange("");
    setHighlight(0);
    setDismissedFor("");
    onCommand(command);
    inputRef.current?.focus();
  }

  function takeFiles(files: FileList | File[] | null | undefined) {
    if (!files || !onAttachFiles) {
      return;
    }
    const list = Array.from(files);
    if (list.length) {
      onAttachFiles(list);
    }
  }

  function onTextareaKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (paletteOpen) {
      // The palette owns Escape while it is open; closing it must not also
      // cancel the reply the user is still reading.
      if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        event.preventDefault();
        if (!matches.length) {
          return;
        }
        const delta = event.key === "ArrowDown" ? 1 : -1;
        setHighlight((index) => (index + delta + matches.length) % matches.length);
        return;
      }
      if ((event.key === "Enter" || event.key === "Tab") && activeCommand) {
        event.preventDefault();
        choose(activeCommand);
        return;
      }
      if (event.key === "Escape") {
        event.preventDefault();
        setDismissedFor(value);
        return;
      }
    }

    if (event.key === "Escape" && streaming) {
      // Keyboard-only readers should not have to tab to the stop button, and
      // an Escape that stops a run is not also a request to close the lens.
      event.preventDefault();
      event.stopPropagation();
      onStop();
      return;
    }

    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      if (canSend) {
        onSubmit();
      }
    }
  }

  return (
    <div
      className={`composer${dragging ? " is-dragging" : ""}`}
      onDragOver={(event) => {
        if (!onAttachFiles || !event.dataTransfer.types.includes("Files")) {
          return;
        }
        event.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(event) => {
        if (!onAttachFiles || !event.dataTransfer.files.length) {
          return;
        }
        event.preventDefault();
        setDragging(false);
        takeFiles(event.dataTransfer.files);
      }}
    >
      {paletteOpen && (
        <div className="palette" role="listbox" id="studio-command-palette" aria-label="Commands">
          {matches.length ? (
            matches.map((command, index) => (
              <button
                key={command.id}
                id={optionId(command)}
                type="button"
                role="option"
                aria-selected={index === activeIndex}
                className={`palette__item${index === activeIndex ? " is-active" : ""}`}
                onMouseEnter={() => setHighlight(index)}
                onClick={() => choose(command)}
              >
                <code className="palette__name">{command.name}</code>
                <span className="palette__text">
                  <span className="palette__label">{command.label}</span>
                  <span className="palette__description">{command.description}</span>
                </span>
              </button>
            ))
          ) : (
            <p className="palette__empty">
              No command matches. Type <code>/help</code> for the full list.
            </p>
          )}
        </div>
      )}

      {connectorSuggestions.length > 0 && (
        <div className="composer__suggestions" aria-label="Connector suggestions">
          {connectorSuggestions.map((id) => {
            const label = presets.find((preset) => preset.id === id)?.label ?? id;
            return (
              <button
                key={id}
                type="button"
                className="composer__suggestion"
                aria-label={`Added ${label}, dismiss`}
                onClick={() => {
                  dismissConnectorSuggestion(id);
                  void refreshConnectors();
                }}
              >
                <span>Added {label}</span>
                <span aria-hidden>✕</span>
              </button>
            );
          })}
        </div>
      )}

      {attachments.length > 0 && (
        <ul className="attach-tray" aria-label="Attached files">
          {attachments.map((attachment) => (
            <li className="attach" key={attachment.id}>
              {isImage(attachment) && attachment.preview_url ? (
                <img className="attach__thumb" src={attachment.preview_url} alt="" />
              ) : (
                <span className="attach__thumb attach__thumb--file" aria-hidden="true">
                  <FileIcon size={14} />
                </span>
              )}
              <span className="attach__text">
                <span className="attach__name">{attachment.name}</span>
                <span className="attach__meta">{formatBytes(attachment.size)}</span>
              </span>
              <button
                type="button"
                className="attach__remove"
                aria-label={`Remove ${attachment.name}`}
                onClick={() => onRemoveAttachment?.(attachment.id)}
              >
                ✕
              </button>
            </li>
          ))}
        </ul>
      )}

      {attachmentError ? (
        <p className="composer__attach-error" role="status">
          {attachmentError}
        </p>
      ) : null}

      <form
        className="composer__shell"
        onSubmit={(event) => {
          event.preventDefault();
          if (canSend) {
            onSubmit();
          }
        }}
      >
        <label className="sr-only" htmlFor="studio-composer">
          Message the studio
        </label>
        <textarea
          id="studio-composer"
          ref={inputRef}
          className="composer__input"
          rows={1}
          value={value}
          placeholder={
            placeholder ??
            (offline
              ? "Model offline — type / for commands, or capture what you know…"
              : "What do you want to make happen?")
          }
          aria-expanded={paletteOpen}
          aria-controls={paletteOpen ? "studio-command-palette" : undefined}
          aria-autocomplete="list"
          aria-activedescendant={
            paletteOpen && activeCommand ? optionId(activeCommand) : undefined
          }
          aria-describedby={HINT_ID}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={onTextareaKeyDown}
          onPaste={(event) => {
            // A pasted screenshot is an attachment, not text.
            const pasted = Array.from(event.clipboardData.files);
            if (!pasted.length || !onAttachFiles) {
              return;
            }
            event.preventDefault();
            takeFiles(pasted);
          }}
        />
        <div className="composer__actions">
          {onAttachFiles ? (
            <>
              <input
                ref={fileInput}
                id={FILES_ID}
                className="sr-only"
                type="file"
                multiple
                accept="image/*,text/*,application/json,application/xml,application/yaml,application/x-yaml,application/toml,application/csv"
                onChange={(event) => {
                  takeFiles(event.target.files);
                  // Allow re-picking the same file after removing it.
                  event.target.value = "";
                }}
              />
              <button
                type="button"
                className="composer__attach"
                aria-label="Attach a file"
                disabled={!canAttach}
                title={
                  canAttach
                    ? "Attach an image or a text file"
                    : `Up to ${MAX_ATTACHMENTS} files at a time`
                }
                onClick={() => fileInput.current?.click()}
              >
                <PaperclipIcon size={16} />
              </button>
            </>
          ) : null}
          {streaming ? (
            <button
              type="button"
              className="composer__send composer__send--stop"
              aria-label="Stop generating"
              onClick={onStop}
            >
              <StopIcon size={16} />
            </button>
          ) : (
            <button
              type="submit"
              className="composer__send"
              aria-label="Send message"
              disabled={!canSend}
            >
              <ArrowUpIcon size={18} />
            </button>
          )}
        </div>
      </form>
      <p className="composer__hint" id={HINT_ID}>
        <span>
          {streaming ? (
            <>
              <kbd>Esc</kbd> to stop
            </>
          ) : (
            <>
              <kbd>Enter</kbd> to send · <kbd>/</kbd> for commands
            </>
          )}
          {brief ? ` · ${brief.product_name || "your job"}` : ""}
        </span>
        <ModelPicker offline={offline} />
      </p>
    </div>
  );
}
