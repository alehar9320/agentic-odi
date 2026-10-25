/**
 * Chrome shared by both composers.
 *
 * The thread composer is bound to the assistant-ui runtime (attachments, stop,
 * queueing); the setup wizard's composer is a controlled textarea because its
 * turns are local until the context is saved. The command palette, the
 * connector chips, and the hint row are the same in both, so they live here.
 */

import type { ReactNode } from "react";

import { isCommandDraft, type StudioCommand } from "../../lib/commands";
import { useStudio } from "../../state/StudioContext";

export function CommandPalette({
  id,
  open,
  matches,
  activeIndex,
  onHover,
  onChoose,
}: {
  /** Unique per composer: two composers can be mounted at once. */
  id: string;
  open: boolean;
  matches: StudioCommand[];
  activeIndex: number;
  onHover: (index: number) => void;
  onChoose: (command: StudioCommand) => void;
}) {
  if (!open) {
    return null;
  }

  return (
    <div className="palette" role="listbox" id={id} aria-label="Commands">
      {matches.length ? (
        matches.map((command, index) => (
          <button
            key={command.id}
            type="button"
            role="option"
            aria-selected={index === activeIndex}
            className={`palette__item${index === activeIndex ? " is-active" : ""}`}
            onMouseEnter={() => onHover(index)}
            onClick={() => onChoose(command)}
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
  );
}

export function ConnectorChips() {
  const {
    connectorSuggestions,
    presets,
    dismissConnectorSuggestion,
    refreshConnectors,
  } = useStudio();

  if (connectorSuggestions.length === 0) {
    return null;
  }

  return (
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
  );
}

export function ComposerHint({ trailing }: { trailing?: ReactNode } = {}) {
  const { settings, llmHealth, brief } = useStudio();
  const offline = llmHealth.healthy === false;

  return (
    <div className="composer__hint">
      <span>
        <kbd>Enter</kbd> to send · <kbd>/</kbd> for commands
        {brief ? ` · ${brief.product_name || "your job"}` : ""}
      </span>
      <span className="composer__hint-end">
        {offline ? <span className="composer__status is-offline">Local guidance</span> : null}
        {trailing ??
          (offline ? null : <span className="composer__status">{settings.model_name}</span>)}
      </span>
    </div>
  );
}

/** Whether a draft should open the command palette. */
export function paletteOpenFor(value: string): boolean {
  return isCommandDraft(value);
}
