import { useEffect, useRef } from "react";

import { useFocusTrap } from "../../lib/useFocusTrap";
import type { BulkReport, Step, StudioError, Theme } from "../../types";

const FIELD_LABEL: Record<BulkReport["changes"][number]["field"], string> = {
  step_id: "Job step",
  theme_ids: "Themes",
  tags: "Tags",
};

/**
 * A before/after image as the person reads it: a theme and a step are named, an
 * empty set is drawn as nothing rather than as a blank cell, and an id the board
 * has no name for is shown as itself instead of guessed at.
 */
function describeValue(
  field: keyof typeof FIELD_LABEL,
  value: string | string[] | null,
  themes: Theme[],
  steps: Step[],
): string {
  if (value === null || value === undefined) {
    return "—";
  }
  const list = Array.isArray(value) ? value : [value];
  if (!list.length) {
    return "—";
  }
  return list
    .map((entry) => {
      if (field === "theme_ids") {
        return themes.find((theme) => theme.id === entry)?.name ?? entry;
      }
      if (field === "step_id") {
        return steps.find((step) => step.id === entry)?.name ?? entry;
      }
      return entry;
    })
    .join(", ");
}

interface BulkChangeDialogProps {
  report: BulkReport;
  /** `preview` offers the write; `applied` reports it and offers the way back. */
  mode: "preview" | "applied";
  error: StudioError | null;
  themes: Theme[];
  steps: Step[];
  busy: boolean;
  onApply: () => void;
  onUndo: () => void;
  onClose: () => void;
}

/**
 * The change table, in the service's own words.
 *
 * A run that skipped rows says so with the count and the reasons: nothing here is
 * worded as success when the write only partly landed, and the numbers come from
 * the report, never from the rows still on screen.
 */
export function BulkChangeDialog({
  report,
  mode,
  error,
  themes,
  steps,
  busy,
  onApply,
  onUndo,
  onClose,
}: BulkChangeDialogProps) {
  const dialogRef = useRef<HTMLDivElement>(null);
  useFocusTrap(dialogRef, true);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onClose();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  const applied = mode === "applied";

  return (
    <div className="studio-bulk-overlay">
      <button
        type="button"
        className="studio-bulk-scrim"
        aria-label="Close the change table"
        tabIndex={-1}
        onClick={onClose}
      />
      <div
        ref={dialogRef}
        className="studio-bulk-modal fade-in"
        role="dialog"
        aria-modal="true"
        aria-labelledby="bulk-dialog-title"
      >
        <header className="studio-bulk-modal__header">
          <h2 className="studio-bulk-modal__title" id="bulk-dialog-title">
            {applied ? "Bulk change applied" : "Bulk change preview"}
          </h2>
          <button type="button" className="studio-bulk-modal__close" aria-label="Close" onClick={onClose}>
            ✕
          </button>
        </header>

        <p className="caption" role="status">
          {applied
            ? `${report.changed.length} changed · ${report.skipped.length} skipped`
            : `${report.requested} outcome${report.requested === 1 ? "" : "s"} asked about, ${
                report.changed.length
              } would change`}
        </p>

        {error ? (
          <p className="studio-bulk-modal__error" role="alert">
            {error.message}
          </p>
        ) : null}

        <div className="studio-bulk-modal__body">
          <table className="studio-bulk-table">
            <thead>
              <tr>
                <th scope="col">Outcome</th>
                <th scope="col">Field</th>
                <th scope="col">From</th>
                <th scope="col">To</th>
              </tr>
            </thead>
            <tbody>
              {report.changes.map((change, index) => (
                <tr key={`${change.outcome_id}:${change.field}:${index}`}>
                  <td>{change.outcome_id}</td>
                  <td>{FIELD_LABEL[change.field]}</td>
                  <td>{describeValue(change.field, change.from, themes, steps)}</td>
                  <td>{describeValue(change.field, change.to, themes, steps)}</td>
                </tr>
              ))}
            </tbody>
          </table>

          {report.skipped.length ? (
            <>
              <h3 className="studio-bulk-modal__subtitle">Skipped by the service</h3>
              <ul className="studio-bulk-modal__skipped" aria-label="Rows this run skipped">
                {report.skipped.map((row) => (
                  <li key={`${row.id}:${row.reason}`}>
                    <b>{row.id}</b> — {row.reason}
                  </li>
                ))}
              </ul>
            </>
          ) : null}
        </div>

        <footer className="studio-bulk-modal__actions">
          {!applied ? (
            <button
              type="button"
              className="studio-button studio-button--primary"
              disabled={busy || !report.changed.length}
              onClick={onApply}
            >
              Apply to {report.changed.length} outcome{report.changed.length === 1 ? "" : "s"}
            </button>
          ) : (
            <button type="button" className="studio-button" disabled={busy} onClick={onUndo}>
              Undo this run
            </button>
          )}
          <button type="button" className="quiet-action" onClick={onClose}>
            {applied ? "Done" : "Keep drafting"}
          </button>
        </footer>
      </div>
    </div>
  );
}
