import { useEffect, useMemo, useState, type RefObject } from "react";

import { isCommandDraft, matchCommands, type StudioCommand } from "../../lib/commands";
import { useStudio } from "../../state/StudioContext";
import { ArrowUpIcon, StopIcon } from "../icons";

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
}

const MAX_HEIGHT = 220;

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
}: ComposerProps) {
  const { settings, llmHealth, brief, connectorSuggestions, presets, dismissConnectorSuggestion, refreshConnectors } =
    useStudio();
  const [highlight, setHighlight] = useState(0);
  // Remember which draft was dismissed, so typing again re-opens the palette
  // without an effect that writes state on every keystroke.
  const [dismissedFor, setDismissedFor] = useState<string | null>(null);

  const offline = llmHealth.healthy === false;
  const matches = useMemo(() => (isCommandDraft(value) ? matchCommands(value) : []), [value]);
  const paletteOpen = isCommandDraft(value) && dismissedFor !== value;

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

  const canSend = value.trim().length > 0 && !streaming;
  const activeIndex = Math.min(highlight, Math.max(matches.length - 1, 0));
  const activeCommand = matches[activeIndex];

  function choose(command: StudioCommand) {
    onChange("");
    setHighlight(0);
    setDismissedFor("");
    onCommand(command);
    inputRef.current?.focus();
  }

  function onTextareaKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (paletteOpen) {
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

    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      if (canSend) {
        onSubmit();
      }
    }
  }

  return (
    <div className="composer">
      {paletteOpen && (
        <div className="palette" role="listbox" id="studio-command-palette" aria-label="Commands">
          {matches.length ? (
            matches.map((command, index) => (
              <button
                key={command.id}
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
                aria-label={`Dismiss suggestion: ${label}`}
                onClick={() => {
                  dismissConnectorSuggestion(id);
                  void refreshConnectors();
                }}
              >
                <span>Suggested: {label}</span>
                <span aria-hidden>✕</span>
              </button>
            );
          })}
        </div>
      )}

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
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={onTextareaKeyDown}
        />
        <div className="composer__actions">
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
      <p className="composer__hint">
        <span>
          <kbd>Enter</kbd> to send · <kbd>/</kbd> for commands
          {brief ? ` · ${brief.product_name || "your job"}` : ""}
        </span>
        <span className={`composer__status${offline ? " is-offline" : ""}`}>
          {offline ? "Local guidance" : settings.model_name}
        </span>
      </p>
    </div>
  );
}
