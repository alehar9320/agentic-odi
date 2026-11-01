import { useCallback, useEffect, useId, useRef } from "react";

import { useOnboarding } from "./context";
import { SCENES } from "./content";
import { LAST_SCENE_INDEX } from "./machine";
import { TourSceneBody } from "./steps";
import "./onboarding.css";

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), ' +
  'textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

/**
 * The tour shell. Three scenes on one sample brief, behind a dialog that traps
 * focus and restores it. Every scene shows its own skip controls, so leaving is
 * never hidden in a footer, and Escape is the same one click.
 */
export function FirstRunWizard() {
  const { enabled, open, state, advance, skipScene, back, complete, skip } = useOnboarding();

  const panelRef = useRef<HTMLDivElement>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);
  const openerRef = useRef<HTMLElement | null>(null);
  const titleId = useId();
  const leadId = useId();

  const sceneIndex = state.scene;
  const scene = SCENES[sceneIndex];
  const isLast = sceneIndex >= LAST_SCENE_INDEX;

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
        skip("dismissed");
      }
    }
    window.addEventListener("keydown", onWindowKeyDown);
    return () => window.removeEventListener("keydown", onWindowKeyDown);
  }, [open, skip]);

  // Each scene announces itself by moving focus to its heading.
  useEffect(() => {
    if (open) {
      headingRef.current?.focus();
    }
  }, [open, sceneIndex]);

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

    // The scene heading holds the initial focus; a Tab from there must not
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
          <span className="wizard-wordmark">{scene.label}</span>
          <span className="wizard-count">
            Scene {sceneIndex + 1} of {SCENES.length}
          </span>
        </header>

        <ol className="wizard-progress" aria-hidden="true">
          {SCENES.map((entry, index) => (
            <li
              key={entry.id}
              className={
                index < sceneIndex
                  ? "wizard-progress__item is-done"
                  : index === sceneIndex
                    ? "wizard-progress__item is-current"
                    : "wizard-progress__item"
              }
            />
          ))}
        </ol>

        <p className="sr-only">
          Scene {sceneIndex + 1} of {SCENES.length}: {scene.label}
        </p>

        <div className="wizard-body" key={scene.id}>
          <h2 className="wizard-title" id={titleId} ref={headingRef} tabIndex={-1}>
            {scene.title}
          </h2>
          <p className="wizard-lead" id={leadId}>
            {scene.lead}
          </p>

          <TourSceneBody scene={sceneIndex} />
        </div>

        <footer className="wizard-footer">
          <div className="wizard-footer__skips">
            <button
              type="button"
              className="wizard-text-button"
              onClick={() => skip("not-now")}
            >
              Skip the tour
            </button>
            {!isLast ? (
              <button type="button" className="wizard-text-button" onClick={skipScene}>
                Skip this scene
              </button>
            ) : null}
          </div>
          <div className="wizard-footer__actions">
            {sceneIndex > 0 ? (
              <button type="button" className="button button--ghost" onClick={back}>
                Back
              </button>
            ) : null}

            <button
              type="button"
              className="button wizard-button--primary"
              onClick={isLast ? complete : advance}
            >
              {isLast ? "Done" : "Continue"}
            </button>
          </div>
        </footer>
      </div>
    </div>
  );
}
