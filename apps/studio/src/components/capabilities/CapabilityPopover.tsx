import { useEffect, useRef, useState } from "react";

import {
  capabilityCatalogue,
  type Capability,
  type CapabilityId,
} from "../../bff/capabilities/registry";
import { useFocusTrap } from "../../lib/useFocusTrap";
import { useStudio } from "../../state/StudioContext";
import { SignalIcon } from "../icons";

export type CapabilityState = "works" | "needs-model" | "needs-service" | "unknown";

export interface CapabilityRow {
  id: CapabilityId;
  label: string;
  description: string;
  state: CapabilityState;
  /** The one word this surface says for the state. */
  word: string;
  /** Why the state is what it is: a probe's own reason, else the description. */
  reason: string;
}

const WORD_FOR_STATE: Record<CapabilityState, string> = {
  works: "Works here",
  "needs-model": "Needs a model",
  "needs-service": "Needs the local service",
  unknown: "Unknown — not checked yet",
};

/**
 * What each capability needs when a probe says it is unavailable. The three
 * `none` capabilities are local and always present; if one is somehow absent we
 * say Unknown rather than name a requirement the registry does not model.
 */
const REQUIREMENT: Record<CapabilityId, "none" | "model" | "service"> = {
  "local-data": "none",
  "local-memory": "none",
  "deterministic-assistant": "none",
  "browser-model": "model",
  "endpoint-model": "model",
  "sidecar-llm": "service",
  "sidecar-connectors": "service",
  "sidecar-mcp": "service",
  "sidecar-import": "service",
};

function stateFor(id: CapabilityId, probed: Capability | undefined): CapabilityState {
  // A capability no probe has reached is unknown, never working: an empty list
  // is not evidence that anything is missing or that anything is present.
  if (!probed) return "unknown";
  if (probed.status === "available") return "works";
  const requirement = REQUIREMENT[id];
  if (requirement === "model") return "needs-model";
  if (requirement === "service") return "needs-service";
  return "unknown";
}

/** One row per capability the registry models, in registry order. */
export function describeCapabilities(capabilities: Capability[]): CapabilityRow[] {
  return capabilityCatalogue.map((entry) => {
    const probed = capabilities.find((capability) => capability.id === entry.id);
    const state = stateFor(entry.id, probed);
    return {
      ...entry,
      state,
      word: WORD_FOR_STATE[state],
      reason: probed?.reason ?? entry.description,
    };
  });
}

/**
 * One quiet control that answers "what works here". It reads the capability
 * registry — the single source of capability truth — and says each capability's
 * state in words, so the answer is not scattered across banners. It carries no
 * badge and no red dot: the state lives in the label text alone.
 */
export function CapabilityPopover() {
  const { capabilities, openSetup } = useStudio();
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  const rows = describeCapabilities(capabilities ?? []);
  const needsService = rows.some((row) => row.state === "needs-service");

  useFocusTrap(dialogRef, open);

  useEffect(() => {
    if (!open) {
      return;
    }
    // The trap focuses the first focusable control; when the dialog holds none,
    // focus the container itself so a keyboard reader is still inside it.
    if (!dialogRef.current?.contains(document.activeElement)) {
      dialogRef.current?.focus();
    }
    function onPointerDown(event: MouseEvent) {
      if (wrapRef.current && !wrapRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false);
      }
    }
    window.addEventListener("mousedown", onPointerDown);
    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("mousedown", onPointerDown);
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  return (
    <div className="bar__menu" ref={wrapRef}>
      <button
        type="button"
        className="icon-button"
        aria-label="What works here"
        aria-haspopup="dialog"
        aria-expanded={open}
        title="What works here"
        onClick={() => setOpen((value) => !value)}
      >
        <SignalIcon size={17} />
      </button>
      {open && (
        <div
          ref={dialogRef}
          className="bar__menu-list capability-popover"
          role="dialog"
          aria-label="What works here"
          tabIndex={-1}
        >
          <p className="capability-popover__title">What works here</p>
          <ul className="capability-popover__list">
            {rows.map((row) => (
              <li key={row.id} className="capability-popover__row">
                <span className="capability-popover__label">{row.label}</span>
                <span className="capability-popover__word">{row.word}</span>
                <span className="capability-popover__reason">{row.reason}</span>
              </li>
            ))}
          </ul>
          {needsService && (
            <button
              type="button"
              className="capability-popover__action"
              onClick={() => {
                setOpen(false);
                openSetup();
              }}
            >
              Start the local service
            </button>
          )}
        </div>
      )}
    </div>
  );
}
