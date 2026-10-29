/**
 * Chrome shared by both composers.
 *
 * The thread composer is bound to the assistant-ui runtime (attachments, stop,
 * queueing); the setup wizard's composer is a controlled textarea because its
 * turns are local until the context is saved. The command palette, the
 * connector chips, and the hint row are the same in both, so they live here.
 */

import { type ReactNode } from "react";
import { useAuiState } from "@assistant-ui/react";
import { isCommandDraft, type StudioCommand } from "../../lib/commands";
import { useStudio } from "../../state/StudioContext";
import { BoltIcon, CaptureIcon, CompassIcon, SparkIcon } from "../icons";

const PILL_ICONS: ReactNode[] = [
  <SparkIcon size={15} key="spark" />,
  <BoltIcon size={15} key="bolt" />,
  <CaptureIcon size={15} key="capture" />,
];

interface QuickPill {
  id: string;
  label: string;
  icon: ReactNode;
  run: () => void;
  conversational?: boolean;
}

export function SuggestionPills() {
  const { canvas, llmHealth, openPanel, streaming, sendMessage } = useStudio();
  const suggestions = useAuiState((state) => state.thread.suggestions);

  const jobs = canvas?.jobs.length ?? 0;

  const pills: QuickPill[] = suggestions.map((suggestion, index) => ({
    id: `suggestion-${index}`,
    label: suggestion.title ?? suggestion.prompt,
    icon: PILL_ICONS[index % PILL_ICONS.length],
    run: () => void sendMessage(suggestion.prompt),
    conversational: true,
  }));

  pills.push(
    jobs > 0 && llmHealth.healthy === false
      ? {
          id: "capture",
          label: "Capture what you heard",
          icon: <CaptureIcon size={15} />,
          run: () => openPanel("capture"),
        }
      : {
          id: "landscape",
          label: "Opportunity landscape",
          icon: <CompassIcon size={15} />,
          run: () => openPanel("landscape"),
        },
  );

  return (
    <div className="composer__pills" aria-label="Suggested next steps">
      {pills.map((pill) => (
        <button
          key={pill.id}
          type="button"
          className="suggestion"
          disabled={Boolean(pill.conversational && streaming)}
          onClick={pill.run}
        >
          {pill.icon}
          {pill.label}
        </button>
      ))}
    </div>
  );
}

export function CommandPalette({
  open,
  matches,
  activeIndex,
  onHover,
  onChoose,
}: {
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
    <div className="palette" role="listbox" id="studio-command-palette" aria-label="Commands">
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

export function ComposerHint() {
  const { settings, llmHealth, brief } = useStudio();
  const offline = llmHealth.healthy === false;

  return (
    <p className="composer__hint">
      <span>
        <kbd>Enter</kbd> to send · <kbd>/</kbd> for commands
        {brief ? ` · ${brief.product_name || "your job"}` : ""}
      </span>
      <span className={`composer__status${offline ? " is-offline" : ""}`}>
        {offline ? "Local guidance" : settings.model_name}
      </span>
    </p>
  );
}

/** Whether a draft should open the command palette. */
export function paletteOpenFor(value: string): boolean {
  return isCommandDraft(value);
}
