import { useEffect, type RefObject } from "react";

import { useStudio } from "../../state/StudioContext";
import { ArrowUpIcon, StopIcon } from "../icons";

interface ComposerProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: (text?: string) => void;
  streaming: boolean;
  onStop: () => void;
  inputRef: RefObject<HTMLTextAreaElement | null>;
  autoFocus?: boolean;
}

const MAX_HEIGHT = 220;

export function Composer({
  value,
  onChange,
  onSubmit,
  streaming,
  onStop,
  inputRef,
  autoFocus = false,
}: ComposerProps) {
  const { settings, llmHealth } = useStudio();

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

  return (
    <div className="composer">
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
          placeholder="Ask about a job, an outcome, or what to build next…"
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
              event.preventDefault();
              if (canSend) {
                onSubmit();
              }
            }
          }}
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
          <kbd>Enter</kbd> to send · <kbd>Shift</kbd>+<kbd>Enter</kbd> for a new line
        </span>
        <span className={`composer__status${llmHealth.healthy === false ? " is-offline" : ""}`}>
          {settings.model_name}
        </span>
      </p>
    </div>
  );
}
