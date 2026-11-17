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
import { ThreadPrimitive, useAuiState } from "@assistant-ui/react";

import { isCommandDraft, type StudioCommand } from "../../lib/commands";
import { useReducedMotion } from "../../lib/useReducedMotion";
import { useStudio } from "../../state/StudioContext";
import { detectPlatform, shortcutLabels } from "../../updater/platform";
import { BoltIcon, CaptureIcon, SparkIcon } from "../icons";

const STARTER_ICONS: ReactNode[] = [
  <SparkIcon size={16} key="spark" />,
  <BoltIcon size={16} key="bolt" />,
  <CaptureIcon size={16} key="capture" />,
];

/**
 * The runtime's suggestions, pinned to the composer so they stay reachable
 * once the thread starts. What is offered here and what the thread knows are
 * the same store, so they cannot drift apart.
 *
 * Each starter is a card with one anatomy — icon, title, artifact preview, one
 * action — in a grid that never wraps mid-set (#317). assistant-ui's
 * `ThreadPrimitive.Suggestion` owns the click: it sends the prompt through the
 * runtime (queueing a follow-up mid-answer instead of swallowing it), so the
 * card carries no submission path of its own (#996). The panel opener
 * ("Opportunity landscape", or the capture fallback) is a quiet text action
 * under the grid, never a fourth card.
 *
 * The list is still ours, not `ThreadPrimitive.Suggestions`, because the card's
 * artifact preview lives on the canvas suggestion and does not survive the
 * runtime's suggestion store (which keeps only title, label, and prompt). The
 * preview is read from `state.thread.suggestions`, the same ordered list the
 * primitive would render.
 */
export function SuggestionPills() {
  const { canvas, llmHealth, openPanel } = useStudio();
  const suggestions = useAuiState((state) => state.thread.suggestions);

  const jobs = canvas?.jobs.length ?? 0;

  const aside =
    jobs > 0 && llmHealth.healthy === false
      ? { label: "Capture what you heard", run: () => openPanel("capture") }
      : { label: "Opportunity landscape", run: () => openPanel("landscape") };

  return (
    <div className="composer__starters" aria-label="Suggested next steps">
      <ul className="starter-grid" role="list">
        {suggestions.map((suggestion, index) => {
          const id = `suggestion-${index}`;
          const title = suggestion.title ?? suggestion.prompt;
          const action = suggestion.label ?? "";
          const artifact = (suggestion as { artifact?: string }).artifact;
          return (
            <li key={id} className="starter-item">
              <ThreadPrimitive.Suggestion
                prompt={suggestion.prompt}
                send
                className="starter"
                aria-label={title}
                aria-describedby={artifact ? `${id}-artifact` : undefined}
              >
                <span className="starter__head">
                  <span className="starter__icon" aria-hidden="true">
                    {STARTER_ICONS[index % STARTER_ICONS.length]}
                  </span>
                  {index === 0 && (
                    <span className="starter__recommended" aria-hidden="true">
                      Recommended
                    </span>
                  )}
                </span>
                <span className="starter__title">{title}</span>
                {artifact && (
                  <span className="starter__artifact" id={`${id}-artifact`}>
                    <span className="starter__artifact-label">Produces</span>
                    {artifact}
                  </span>
                )}
                {action && <span className="starter__action">{action}</span>}
              </ThreadPrimitive.Suggestion>
            </li>
          );
        })}
      </ul>
      <button type="button" className="composer__starter-aside" onClick={aside.run}>
        {aside.label}
      </button>
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
  const reducedMotion = useReducedMotion();

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
