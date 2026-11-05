/**
 * One assistant turn's calls, collapsed into a single row.
 *
 * A finished turn used to leave a column of identical grey lines behind it, one
 * per call, which the reader had to scan in full to learn nothing more than
 * "it looked things up and wrote twice". The row says that in one line and
 * expands, in order, into the same call cards the row replaces.
 */

import { useId, useState, type ReactNode } from "react";

import { formatRunSummary, type RunSummary } from "../../assistant/runSummary";
import { ChevronDownIcon } from "../icons";

type RunRowProps = {
  summary: RunSummary;
  /** The turn is still streaming, so the calls stay visible until it settles. */
  running: boolean;
  /** One call is a question the user has not answered; a row may not hide it. */
  requiresAction: boolean;
  children: ReactNode;
};

export function RunRow({ summary, running, requiresAction, children }: RunRowProps) {
  const panelId = useId();
  // null: nobody has touched the row, so the turn's own state decides.
  const [chosen, setChosen] = useState<boolean | null>(null);

  if (summary.calls === 0) {
    return null;
  }
  const open = requiresAction || (chosen ?? running);

  return (
    <div className={`run-summary${running ? " is-running" : ""}`}>
      <button
        type="button"
        className="run-summary__toggle"
        aria-expanded={open}
        aria-controls={panelId}
        disabled={requiresAction}
        onClick={() => setChosen(!open)}
      >
        <span className="run-summary__dot" aria-hidden="true" />
        <span className="run-summary__label">{formatRunSummary(summary)}</span>
        <ChevronDownIcon
          className={`run-summary__chevron${open ? " is-open" : ""}`}
          size={12}
        />
      </button>
      <div className="run-summary__panel" id={panelId} hidden={!open}>
        {children}
      </div>
    </div>
  );
}
