import { useId, type ReactNode } from "react";

import { BoltIcon, CompassIcon, SignalIcon, SparkIcon } from "../components/icons";
import { GOALS, type GoalIconName, type GoalId, type OnboardingGoal } from "./content";

/* ------------------------------------------------------------------ */
/* Shared                                                             */
/* ------------------------------------------------------------------ */

const ICONS: Record<GoalIconName, ReactNode> = {
  spark: <SparkIcon size={18} />,
  bolt: <BoltIcon size={18} />,
  compass: <CompassIcon size={18} />,
  signal: <SignalIcon size={18} />,
};

function GoalIcon({ name }: { name: GoalIconName }) {
  return (
    <span className="wizard-goal__icon" aria-hidden="true">
      {ICONS[name]}
    </span>
  );
}

/* ------------------------------------------------------------------ */
/* Step 1 — what this is                                              */
/* ------------------------------------------------------------------ */

const MOVES = [
  {
    index: "01",
    title: "Name the opportunity",
    detail: "Say it the way you'd say it to your boss. We'll make it precise.",
  },
  {
    index: "02",
    title: "Find the evidence",
    detail: "See what customers actually feel, and where the gap is widest.",
  },
  {
    index: "03",
    title: "Choose and defend",
    detail: "Leave with a thesis, a next move, and what would change your mind.",
  },
];

export function WelcomeStep() {
  return (
    <ul className="wizard-moves">
      {MOVES.map((move) => (
        <li className="wizard-move" key={move.index}>
          <span className="wizard-move__index" aria-hidden="true">
            {move.index}
          </span>
          <span>
            <span className="wizard-move__title">{move.title}</span>
            <span className="wizard-move__detail">{move.detail}</span>
          </span>
        </li>
      ))}
    </ul>
  );
}

/* ------------------------------------------------------------------ */
/* Step 2 — one starting point                                        */
/* ------------------------------------------------------------------ */

export function GoalStep({
  goal,
  onSelect,
}: {
  goal: GoalId | null;
  onSelect: (goal: GoalId) => void;
}) {
  return (
    <>
      <div className="wizard-goals" role="group" aria-label="Choose a starting point">
        {GOALS.map((option) => {
          const selected = option.id === goal;
          return (
            <button
              key={option.id}
              type="button"
              className="wizard-goal"
              aria-pressed={selected}
              onClick={() => onSelect(option.id)}
            >
              <GoalIcon name={option.icon} />
              <span className="wizard-goal__copy">
                <span className="wizard-goal__title">
                  {option.title}
                  {selected ? (
                    <span className="wizard-goal__check" aria-hidden="true">
                      ✓
                    </span>
                  ) : null}
                </span>
                <span className="wizard-goal__blurb">{option.blurb}</span>
              </span>
            </button>
          );
        })}
      </div>
      <p className="wizard-hint">
        {goal
          ? "Continue when you are ready. Everything stays one message away."
          : "Pick one to start."}
      </p>
    </>
  );
}

/* ------------------------------------------------------------------ */
/* Step 3 — instruments                                               */
/* ------------------------------------------------------------------ */

export interface ConnectionDraft {
  base_url: string;
  model_name: string;
  api_key: string;
}

export interface ConnectionStatus {
  sidecar: boolean | null;
  mcp: boolean | null;
  model: boolean | null;
}

function StatusRow({
  label,
  detail,
  value,
}: {
  label: string;
  detail: string;
  value: boolean | null;
}) {
  const state = value === true ? "ok" : value === false ? "warn" : "pending";
  const text = value === true ? "Connected" : value === false ? "Not reachable" : "Checking";

  return (
    <div className={`wizard-check wizard-check--${state}`}>
      <span className="wizard-check__dot" aria-hidden="true" />
      <span className="wizard-check__copy">
        <span className="wizard-check__label">{label}</span>
        <span className="wizard-check__detail">{detail}</span>
      </span>
      <span className="wizard-check__state">{text}</span>
    </div>
  );
}

export function ReadinessStep({
  status,
  modelMessage,
  draft,
  onChange,
  onSaveAndTest,
  onRetry,
  busy,
  message,
}: {
  status: ConnectionStatus;
  modelMessage: string;
  draft: ConnectionDraft;
  onChange: (patch: Partial<ConnectionDraft>) => void;
  onSaveAndTest: () => void;
  onRetry: () => void;
  busy: boolean;
  message: string | null;
}) {
  const prefix = useId();
  const modelDown = status.model === false;

  return (
    <>
      <div className="wizard-checks">
        <StatusRow
          label="Studio service"
          detail="The local sidecar serving this window."
          value={status.sidecar}
        />
        <StatusRow
          label="MCP server"
          detail="Your jobs, outcomes, and evidence."
          value={status.mcp}
        />
        <StatusRow
          label="Copilot model"
          detail="The OpenAI-compatible model behind the chat."
          value={status.model}
        />
      </div>

      {modelDown ? (
        <div className="wizard-config">
          <p className="wizard-config__hint">
            The studio still opens and works by hand. Point it at a model now, or connect
            one later in Settings.
          </p>
          {modelMessage ? <p className="wizard-config__message">{modelMessage}</p> : null}

          <div className="wizard-config__grid">
            <div className="field">
              <label htmlFor={`${prefix}-base-url`}>Base URL</label>
              <input
                id={`${prefix}-base-url`}
                className="input"
                value={draft.base_url}
                spellCheck={false}
                onChange={(event) => onChange({ base_url: event.target.value })}
              />
            </div>
            <div className="field">
              <label htmlFor={`${prefix}-model`}>Model</label>
              <input
                id={`${prefix}-model`}
                className="input"
                value={draft.model_name}
                spellCheck={false}
                onChange={(event) => onChange({ model_name: event.target.value })}
              />
            </div>
            <div className="field wizard-config__key">
              <label htmlFor={`${prefix}-api-key`}>API key</label>
              <input
                id={`${prefix}-api-key`}
                className="input"
                type="password"
                autoComplete="off"
                value={draft.api_key}
                onChange={(event) => onChange({ api_key: event.target.value })}
              />
            </div>
          </div>

          <div className="wizard-config__actions">
            <button type="button" className="button" disabled={busy} onClick={onSaveAndTest}>
              {busy ? "Testing…" : "Save & test"}
            </button>
            <button
              type="button"
              className="button button--ghost"
              disabled={busy}
              onClick={onRetry}
            >
              Retry
            </button>
            <span className="wizard-config__status" role="status" aria-live="polite">
              {message}
            </span>
          </div>
        </div>
      ) : (
        <div className="wizard-config__actions">
          <button
            type="button"
            className="button button--ghost"
            disabled={busy}
            onClick={onRetry}
          >
            {busy ? "Checking…" : "Check again"}
          </button>
          <span className="wizard-config__status" role="status" aria-live="polite">
            {message}
          </span>
        </div>
      )}
    </>
  );
}

/* ------------------------------------------------------------------ */
/* Step 4 — first move                                                */
/* ------------------------------------------------------------------ */

export function LaunchStep({ goal }: { goal: OnboardingGoal }) {
  return (
    <div className="wizard-launch">
      <div className="wizard-choice">
        <GoalIcon name={goal.icon} />
        <span>
          <span className="wizard-choice__title">{goal.title}</span>
          <span className="wizard-choice__result">{goal.result}</span>
        </span>
      </div>

      <div className="wizard-destination">
        <p className="wizard-destination__label">Where this goes</p>
        <p className="wizard-destination__detail">{goal.destinationLabel}</p>
      </div>

      <p className="wizard-hint">Replay this tour from Settings whenever you want.</p>
    </div>
  );
}
