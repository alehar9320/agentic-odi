import { useEffect, useRef } from "react";

import { useFocusTrap } from "../../lib/useFocusTrap";
import type { Capability } from "../../bff/capabilities/registry";

/**
 * One word per capability state, in exactly one place, so the bar, the popover,
 * and any future surface cannot drift into a second vocabulary.
 *
 * `unknown` is its own state: a probe that has not run yet must not read as
 * working, and it must not read as broken either. A probe that ran and failed
 * is also unknown — the honest answer is "we checked and do not know", not
 * "works here".
 */
export type CapabilityWord =
  | "Works here"
  | "Needs the local service"
  | "Needs a model"
  | "Unknown — not checked yet";

export interface CapabilityRow {
  id: string;
  label: string;
  description: string;
  word: CapabilityWord;
  reason?: string;
}

const LOCAL_IDS: Capability["id"][] = ["local-data", "local-memory", "deterministic-assistant"];
const SIDECAR_IDS: Capability["id"][] = [
  "sidecar-connectors",
  "sidecar-mcp",
  "sidecar-import",
];
const MODEL_IDS: Capability["id"][] = ["endpoint-model", "browser-model", "sidecar-llm"];

function wordFor(capability: Capability): CapabilityWord {
  if (capability.status !== "available") {
    return "Unknown — not checked yet";
  }
  if (LOCAL_IDS.includes(capability.id)) {
    return "Works here";
  }
  if (SIDECAR_IDS.includes(capability.id)) {
    return "Needs the local service";
  }
  if (MODEL_IDS.includes(capability.id)) {
    return "Needs a model";
  }
  // The registry's CapabilityId union is the nine ids above; anything that
  // reaches this branch is a capability the vocabulary does not yet describe,
  // and saying "Works here" would be a lie. It reads as unknown until someone
  // writes a word for it.
  return "Unknown — not checked yet";
}

/** Map a capability to the words the person should read. */
export function describeCapabilities(capabilities: Capability[]): CapabilityRow[] {
  return capabilities.map((capability) => ({
    id: capability.id,
    label: capability.label,
    description: capability.description,
    word: wordFor(capability),
    ...(capability.reason ? { reason: capability.reason } : {}),
  }));
}

interface CapabilityPopoverProps {
  capabilities: Capability[];
  checkedAt: string | null;
  isOpen: boolean;
  onClose: () => void;
  onOpenSettings: () => void;
}

export function CapabilityPopover({
  capabilities,
  checkedAt,
  isOpen,
  onClose,
  onOpenSettings,
}: CapabilityPopoverProps) {
  const dialogRef = useRef<HTMLDivElement>(null);
  useFocusTrap(dialogRef, isOpen);

  useEffect(() => {
    if (!isOpen) {
      return;
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.stopPropagation();
        onClose();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) {
    return null;
  }

  const rows = describeCapabilities(capabilities);
  // A sidecar that answered is a sidecar that is running; only offer to start
  // one when the probes say it is not there. An empty list is "not checked
  // yet", which is not the same as "down" — offer Settings either way.
  const sidecarDown =
    capabilities.length > 0 &&
    capabilities.some(
      (capability) => capability.id.startsWith("sidecar-") && capability.status !== "available",
    );

  return (
    <div className="capability-popover-wrap">
      <button
        type="button"
        className="capability-scrim"
        aria-label="Close what works here"
        tabIndex={-1}
        onClick={onClose}
      />
      <div
        ref={dialogRef}
        className="capability-popover"
        role="dialog"
        aria-modal="true"
        aria-labelledby="capability-popover-title"
        aria-describedby="capability-popover-subtitle"
      >
        <header className="capability-popover__header">
          <div>
            <span className="capability-popover__badge">WHAT WORKS HERE</span>
            <h2 id="capability-popover-title" className="capability-popover__title">
              What works here
            </h2>
            <p id="capability-popover-subtitle" className="capability-popover__subtitle">
              {checkedAt ? "Checked just now." : "Not checked yet — nothing below is a guess."}
            </p>
          </div>
          <button
            type="button"
            className="capability-popover__close"
            onClick={onClose}
            aria-label="Close what works here"
          >
            ✕
          </button>
        </header>

        <div className="capability-popover__body">
          {rows.length === 0 ? (
            <p className="capability-popover__empty">
              Nothing has been checked yet. Open Settings to run the probes.
            </p>
          ) : (
            <ul className="capability-popover__list">
              {rows.map((row) => (
                <li key={row.id} className="capability-popover__row">
                  <div className="capability-popover__word">
                    <span
                      className={`capability-dot capability-dot--${row.word === "Works here" ? "works" : row.word === "Needs the local service" ? "sidecar" : row.word === "Needs a model" ? "model" : "unknown"}`}
                      aria-hidden="true"
                    />
                    <span className="capability-popover__label">{row.label}</span>
                  </div>
                  <p className="capability-popover__description">{row.description}</p>
                  <p className="capability-popover__state">{row.word}</p>
                  {row.reason ? (
                    <p className="capability-popover__reason">{row.reason}</p>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </div>

        <footer className="capability-popover__footer">
          {sidecarDown ? (
            <button
              type="button"
              className="capability-popover__action"
              onClick={() => {
                onClose();
                onOpenSettings();
              }}
            >
              Start the local service
            </button>
          ) : (
            <button
              type="button"
              className="capability-popover__action capability-popover__action--ghost"
              onClick={() => {
                onClose();
                onOpenSettings();
              }}
            >
              Recheck
            </button>
          )}
          <button
            type="button"
            className="capability-popover__action capability-popover__action--ghost"
            onClick={() => {
              onClose();
              onOpenSettings();
            }}
          >
            Open Settings
          </button>
        </footer>
      </div>
    </div>
  );
}