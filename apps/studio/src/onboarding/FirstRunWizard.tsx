import { useCallback, useEffect, useId, useRef, useState } from "react";

import { useStudio } from "../state/StudioContext";
import { useOnboarding } from "./context";
import { STEPS, goalById, type GoalId } from "./content";
import { LAST_STEP_INDEX, stepAt } from "./machine";
import {
  GoalStep,
  LaunchStep,
  ReadinessStep,
  WelcomeStep,
  type ConnectionDraft,
} from "./steps";
import "./onboarding.css";

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), ' +
  'textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

export function FirstRunWizard() {
  const { enabled, open, state, chooseGoal, advance, back, complete, skip } = useOnboarding();
  const {
    settings,
    saveSettings,
    sidecarReachable,
    mcpReachable,
    llmHealth,
    checkConnections,
    openPanel,
    openSetup,
    closeSetup,
    sendMessage,
  } = useStudio();

  const panelRef = useRef<HTMLDivElement>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);
  const openerRef = useRef<HTMLElement | null>(null);
  const titleId = useId();
  const leadId = useId();

  // The quick-connect fields start from the live config and only diverge once
  // the user edits them, so no effect has to copy state around.
  const [edits, setEdits] = useState<Partial<ConnectionDraft>>({});
  const draft: ConnectionDraft = {
    base_url: edits.base_url ?? settings.base_url,
    model_name: edits.model_name ?? settings.model_name,
    api_key: edits.api_key ?? settings.api_key,
  };
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const stepIndex = state.step;
  const stepId = stepAt(stepIndex);
  const step = STEPS[stepIndex];
  const activeGoal = goalById(state.goal);

  // Probe only what we have not already learned.
  useEffect(() => {
    if (!open || stepId !== "readiness") {
      return;
    }
    if (llmHealth.healthy !== null && sidecarReachable !== null) {
      return;
    }
    void checkConnections().catch(() => undefined);
  }, [
    open,
    stepId,
    checkConnections,
    llmHealth.healthy,
    sidecarReachable,
  ]);

  // Remember where focus came from, and give it back when the dialog closes.
  useEffect(() => {
    if (!open) {
      return;
    }
    const active = document.activeElement;
    openerRef.current = active instanceof HTMLElement ? active : null;
    return () => {
      openerRef.current?.focus();
    };
  }, [open]);

  // The page behind the dialog stays where it was; it just stops scrolling.
  useEffect(() => {
    if (!open) {
      return;
    }
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previous;
    };
  }, [open]);

  // Escape is a document-level escape hatch, not a detail of the panel.
  useEffect(() => {
    if (!open) {
      return;
    }
    function onWindowKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        skip();
      }
    }
    window.addEventListener("keydown", onWindowKeyDown);
    return () => window.removeEventListener("keydown", onWindowKeyDown);
  }, [open, skip]);

  // Each step announces itself by moving focus to its heading.
  useEffect(() => {
    if (open) {
      headingRef.current?.focus();
    }
  }, [open, stepIndex]);

  const onKeyDown = useCallback((event: React.KeyboardEvent<HTMLDivElement>) => {
    if (event.key !== "Tab" || !panelRef.current) {
      return;
    }
    const nodes = Array.from(panelRef.current.querySelectorAll<HTMLElement>(FOCUSABLE));
    if (nodes.length === 0) {
      event.preventDefault();
      panelRef.current.focus();
      return;
    }
    const first = nodes[0];
    const last = nodes[nodes.length - 1];
    const active = document.activeElement;
    const inside = active instanceof HTMLElement && nodes.includes(active);

    // The step heading holds the initial focus; a Tab from there must not
    // escape the dialog either.
    if (!inside) {
      event.preventDefault();
      (event.shiftKey ? last : first).focus();
      return;
    }
    if (event.shiftKey && active === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && active === last) {
      event.preventDefault();
      first.focus();
    }
  }, []);

  async function saveAndTest() {
    const next = {
      ...settings,
      base_url: draft.base_url.trim(),
      model_name: draft.model_name.trim(),
      api_key: draft.api_key.trim(),
    };
    saveSettings(next);
    setBusy(true);
    setMessage(null);
    try {
      const result = await checkConnections(next);
      setEdits({});
      setMessage(
        result.llmHealthy
          ? "The model answered. You are ready."
          : "No answer yet. The studio still works by hand.",
      );
    } catch {
      setMessage("Could not reach the studio service. Is it running?");
    } finally {
      setBusy(false);
    }
  }

  async function retry() {
    setBusy(true);
    setMessage(null);
    try {
      const result = await checkConnections();
      const allAnswered =
        result.sidecarReachable && result.mcpReachable && result.llmHealthy;
      setMessage(
        allAnswered ? "All instruments answered." : "Some instruments did not answer yet.",
      );
    } catch {
      setMessage("Could not reach the studio service. Is it running?");
    } finally {
      setBusy(false);
    }
  }

  function launch() {
    if (!activeGoal) {
      return;
    }
    complete();
    if (activeGoal.destination.kind === "setup") {
      openSetup();
    } else if (activeGoal.destination.kind === "chat") {
      // Some starting points are a conversation, not a view: close the setup
      // questions so the chosen thread has the stage.
      closeSetup();
      void sendMessage(activeGoal.destination.prompt);
    } else {
      openPanel(activeGoal.destination.panel);
    }
  }

  if (!enabled || !open) {
    return null;
  }

  return (
    <div className="wizard-backdrop">
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={leadId}
        className="wizard-panel"
        tabIndex={-1}
        onKeyDown={onKeyDown}
      >
        <header className="wizard-head">
          <span className="wizard-wordmark">The Living Studio</span>
          <span className="wizard-count">
            {stepIndex + 1} / {STEPS.length}
          </span>
        </header>

        <ol className="wizard-progress" aria-hidden="true">
          {STEPS.map((entry, index) => (
            <li
              key={entry.id}
              className={
                index < stepIndex
                  ? "wizard-progress__item is-done"
                  : index === stepIndex
                    ? "wizard-progress__item is-current"
                    : "wizard-progress__item"
              }
            />
          ))}
        </ol>

        <p className="sr-only">
          Step {stepIndex + 1} of {STEPS.length}: {step.label}
        </p>

        <div className="wizard-body" key={stepId}>
          <h2 className="wizard-title" id={titleId} ref={headingRef} tabIndex={-1}>
            {step.title}
          </h2>
          <p className="wizard-lead" id={leadId}>
            {step.lead}
          </p>

          {stepId === "welcome" ? <WelcomeStep /> : null}
          {stepId === "goal" ? (
            <GoalStep goal={state.goal} onSelect={(goal: GoalId) => chooseGoal(goal)} />
          ) : null}
          {stepId === "readiness" ? (
            <ReadinessStep
              status={{
                sidecar: sidecarReachable,
                mcp: mcpReachable,
                model: llmHealth.healthy,
              }}
              modelMessage={llmHealth.message}
              draft={draft}
              onChange={(patch) => setEdits((prev) => ({ ...prev, ...patch }))}
              onSaveAndTest={() => void saveAndTest()}
              onRetry={() => void retry()}
              busy={busy}
              message={message}
            />
          ) : null}
          {stepId === "launch" && activeGoal ? <LaunchStep goal={activeGoal} /> : null}
        </div>

        <footer className="wizard-footer">
          <div>
            {stepIndex < LAST_STEP_INDEX ? (
              <button type="button" className="wizard-text-button" onClick={skip}>
                Skip the tour
              </button>
            ) : null}
          </div>
          <div className="wizard-footer__actions">
            {stepIndex > 0 ? (
              <button
                type="button"
                className="button button--ghost"
                onClick={back}
              >
                Back
              </button>
            ) : null}

            {stepId === "launch" ? (
              <button
                type="button"
                className="button wizard-button--primary"
                onClick={launch}
                disabled={!activeGoal}
              >
                {activeGoal?.cta ?? "Continue"}
              </button>
            ) : (
              <button
                type="button"
                className="button wizard-button--primary"
                onClick={advance}
                disabled={stepId === "goal" && state.goal === null}
              >
                Continue
              </button>
            )}
          </div>
        </footer>
      </div>
    </div>
  );
}
