import { useEffect, useId, useMemo, useState, type RefObject } from "react";

import { isCommandDraft, matchCommands, type StudioCommand } from "../../lib/commands";
import { useStudio } from "../../state/StudioContext";
import { ArrowUpIcon, StopIcon } from "../icons";
import { CommandPalette, ComposerHint, ConnectorChips } from "./composerParts";

/**
 * A controlled composer for conversations the runtime does not own.
 *
 * The setup wizard answers local questions before there is a thread, so it keeps
 * its own text state. The thread's composer is `ThreadComposer`, which is bound
 * to the assistant-ui runtime; the palette, chips, and hint are shared.
 */
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
  const { llmHealth } = useStudio();
  // Two composers can be mounted at once (the thread's and the setup wizard's).
  const inputId = useId();
  const paletteId = useId();
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
  const activeOptionId =
    paletteOpen && matches.length ? `${paletteId}-option-${activeIndex}` : undefined;

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
      <CommandPalette
        id={paletteId}
        open={paletteOpen}
        matches={matches}
        activeIndex={activeIndex}
        onHover={setHighlight}
        onChoose={choose}
      />
      <ConnectorChips />
      <form
        className="composer__shell"
        onSubmit={(event) => {
          event.preventDefault();
          if (canSend) {
            onSubmit();
          }
        }}
      >
        <label className="sr-only" htmlFor={inputId}>
          Message the studio
        </label>
        <textarea
          id={inputId}
          ref={inputRef}
          className="composer__input"
          rows={1}
          value={value}
          placeholder={
            placeholder ??
            (offline
              ? "Model offline — type / for commands, or capture what you know…"
              : "Start with what's on your mind…")
          }
          aria-haspopup="listbox"
          aria-controls={paletteOpen ? paletteId : undefined}
          aria-activedescendant={activeOptionId}
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
      <ComposerHint />
    </div>
  );
}
