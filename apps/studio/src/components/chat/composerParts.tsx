/**
 * Chrome shared by both composers.
 *
 * The thread composer is bound to the assistant-ui runtime (attachments, stop,
 * queueing); the setup wizard's composer is a controlled textarea because its
 * turns are local until the context is saved. The command palette, the
 * connector chips, and the hint row are the same in both, so they live here.
 * The focus chip is the exception: it speaks for the canvas, so only the
 * thread composer mounts it.
 */

import { useEffect, useRef, type ReactNode } from "react";
import { useAuiState } from "@assistant-ui/react";

import { isCommandDraft, type StudioCommand } from "../../lib/commands";
import { usePrefersReducedMotion } from "../../lib/useMediaQuery";
import { useStudio } from "../../state/StudioContext";
import { detectPlatform, shortcutLabels } from "../../updater/platform";
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
}

/**
 * The runtime's suggestions, pinned to the composer so they stay reachable
 * once the thread starts. What is offered here and what the thread knows are
 * the same store, so they cannot drift apart.
 */
export function SuggestionPills() {
  const { canvas, llmHealth, openPanel, sendMessage } = useStudio();
  const suggestions = useAuiState((state) => state.thread.suggestions);

  const jobs = canvas?.jobs.length ?? 0;

  const pills: QuickPill[] = suggestions.map((suggestion, index) => ({
    id: `suggestion-${index}`,
    label: suggestion.title ?? suggestion.prompt,
    icon: PILL_ICONS[index % PILL_ICONS.length],
    run: () => void sendMessage(suggestion.prompt),
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
        <button key={pill.id} type="button" className="suggestion" onClick={pill.run}>
          {pill.icon}
          {pill.label}
        </button>
      ))}
    </div>
  );
}

/**
 * One row of the palette. It keeps itself visible: the highlighted command is
 * scrolled to with `block: "nearest"`, so the list moves as little as it can
 * and never hides the row the person is on.
 */
function PaletteOption({
  id,
  active,
  command,
  onHover,
  onChoose,
}: {
  id: string;
  active: boolean;
  command: StudioCommand;
  onHover: () => void;
  onChoose: () => void;
}) {
  const ref = useRef<HTMLButtonElement | null>(null);
  const reducedMotion = usePrefersReducedMotion();

  useEffect(() => {
    if (!active) {
      return;
    }
    const element = ref.current;
    if (!element || typeof element.scrollIntoView !== "function") {
      return;
    }
    element.scrollIntoView({
      block: "nearest",
      behavior: reducedMotion ? "auto" : "smooth",
    });
  }, [active, reducedMotion]);

  return (
    <button
      ref={ref}
      type="button"
      role="option"
      id={id}
      aria-selected={active}
      className={`palette__item${active ? " is-active" : ""}`}
      onMouseEnter={onHover}
      onClick={onChoose}
    >
      <code className="palette__name">{command.name}</code>
      <span className="palette__text">
        <span className="palette__label">{command.label}</span>
        <span className="palette__description">{command.description}</span>
      </span>
    </button>
  );
}

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
          <PaletteOption
            key={command.id}
            id={`${id}-option-${index}`}
            active={index === activeIndex}
            command={command}
            onHover={() => onHover(index)}
            onChoose={() => onChoose(command)}
          />
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

/**
 * What the agent was told about the screen, so the person can see it, check it,
 * and take it back.
 *
 * Renders only when the canvas can name the selection: a chip for a record this
 * snapshot cannot read would be claiming something the store never said.
 */
export function ContextChip() {
  const { focusedSubject, focusedSubjectLabel, clearFocus, revealFocusedSubject } = useStudio();

  if (!focusedSubject || !focusedSubjectLabel) {
    return null;
  }

  return (
    <div className="composer__focus" role="status">
      <button
        type="button"
        className="composer__focus-chip"
        aria-label={`Looking at: ${focusedSubjectLabel}`}
        onClick={revealFocusedSubject}
      >
        <span>Looking at: {focusedSubjectLabel}</span>
      </button>
      <button
        type="button"
        className="quiet-action"
        aria-label="Stop telling the agent what you are looking at"
        onClick={clearFocus}
      >
        <span aria-hidden>✕</span>
      </button>
    </div>
  );
}

export function ComposerHint({ trailing }: { trailing?: ReactNode } = {}) {
  const { settings, llmHealth, brief } = useStudio();
  const offline = llmHealth.healthy === false;
  // The keycaps are the machine's, not ours: macOS prints ⌘ and ↵ where the
  // other desktops spell them out.
  const keys = shortcutLabels(detectPlatform());

  return (
    <div className="composer__hint">
      <span>
        <kbd>{keys.focus}</kbd> to focus · <kbd>{keys.send}</kbd> to send · <kbd>/</kbd> for
        commands
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
