import { useEffect, useState } from "react";

import { fetchOutcomeHistory, fetchOutcomeInterval } from "../../api/studioApi";
import {
  formatBandProvenance,
  formatOpportunityScore,
  formatSample,
  isUnderserved,
  opportunityPill,
  opportunityScore,
} from "../../lib/odi";
import { useStudio } from "../../state/StudioContext";
import type { Outcome, OutcomeInterval } from "../../types";
import { CopyIcon } from "../icons";

export function OutcomeCard({
  outcome,
  sample = false,
  detail = false,
}: {
  outcome: Outcome;
  sample?: boolean;
  detail?: boolean;
}) {
  const { ask, canvasState, deleteOutcome, pushToast, saveThesis, settings, updateOutcome } =
    useStudio();
  // Records captured against this outcome, with their way back to the source.
  const linkedEvidence = (canvasState.data?.evidence ?? []).filter(
    (item) => item.outcome_id === outcome.id,
  );
  const [showEvidence, setShowEvidence] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [editing, setEditing] = useState(false);
  const [thesisOpen, setThesisOpen] = useState(false);
  const [rationale, setRationale] = useState("");
  const [importance, setImportance] = useState(outcome.importance ?? 5);
  const [satisfaction, setSatisfaction] = useState(outcome.satisfaction ?? 5);
  const [saving, setSaving] = useState(false);
  // The reason recorded with the most recent accepted score change. It is
  // snapshot metadata, not an Outcome field, so it is fetched from history and
  // tagged with its outcome so a switch never shows the previous one's note.
  const [noteFor, setNoteFor] = useState<{ id: string; note: string | null } | null>(null);
  // The stored band and its provenance. Fetched only on the detail card, like
  // the note, so the list does not issue one request per row. A failed fetch
  // leaves the line absent rather than showing a fabricated band.
  const [intervalFor, setIntervalFor] = useState<{
    id: string;
    interval: OutcomeInterval | null;
  } | null>(null);

  const outcomeId = outcome.id ?? "O";
  useEffect(() => {
    const id = outcome.id;
    // Only the detail card reads history: the list renders one card per
    // outcome, and a note there would be one request per row.
    if (!detail || !id || sample) return;
    let cancelled = false;
    void fetchOutcomeHistory(id, settings.mcp_url)
      .then((snapshots) => {
        if (cancelled) return;
        const noted = [...snapshots].reverse().find((snapshot) => snapshot.note);
        setNoteFor({ id, note: noted?.note ?? null });
      })
      .catch(() => {
        // History is supporting context: a failure leaves the line absent
        // rather than blocking the card.
        if (!cancelled) setNoteFor({ id, note: null });
      });
    return () => {
      cancelled = true;
    };
  }, [detail, outcome.id, sample, settings.mcp_url]);

  useEffect(() => {
    const id = outcome.id;
    if (!detail || !id || sample) return;
    let cancelled = false;
    void fetchOutcomeInterval(id, settings.mcp_url)
      .then((interval) => {
        if (!cancelled) setIntervalFor({ id, interval });
      })
      .catch(() => {
        // A failed read leaves the line absent: rendering "no band" would claim
        // the score carries none, which is a different fact from an unread one.
      });
    return () => {
      cancelled = true;
    };
  }, [detail, outcome.id, sample, settings.mcp_url]);

  const latestNote =
    detail && !sample && noteFor && noteFor.id === outcome.id ? noteFor.note : null;
  const interval =
    detail && !sample && intervalFor && intervalFor.id === outcome.id
      ? intervalFor.interval
      : null;

  const opp = outcome.opportunity_score;
  const statement = outcome.statement ?? "Untitled outcome";
  const underserved = isUnderserved(opp);
  const pill = opportunityPill(opp);

  return (
    <article className={`card${underserved ? " card--hot" : ""}`} aria-label={`Outcome ${outcomeId}`}>
      <header className="card__head">
        <span className="card__id">{outcomeId}</span>
        <span className={`badge badge--${pill.variant}`}>{pill.label}</span>
        {sample ? (
          <span
            className="badge badge--amber"
            title="This is bundled sample data, not yours."
          >
            Sample
          </span>
        ) : null}
      </header>

      <p className="card__statement">{statement}</p>

      <p className="card__meta">
        Importance <b>{outcome.importance ?? "—"}</b>
        <span aria-hidden="true"> · </span>
        Satisfaction <b>{outcome.satisfaction ?? "—"}</b>
        <span aria-hidden="true"> · </span>
        Opportunity <b>{formatOpportunityScore(opp)}</b>
        <span aria-hidden="true"> · </span>
        <span title="How many people stand behind each score, and how it was obtained">
          {formatSample(outcome)}
        </span>
      </p>

      {latestNote ? (
        <p className="card__meta" data-testid="outcome-note">
          <span title="The reason recorded with the most recent accepted score change">
            Note <b>{latestNote}</b>
          </span>
        </p>
      ) : null}

      {detail && !sample && intervalFor?.id === outcome.id ? (
        <p className="card__meta" data-testid="outcome-band-provenance">
          <span title="The stored band and the provenance it was recorded with">
            Band <b>{formatBandProvenance(interval)}</b>
          </span>
        </p>
      ) : null}

      {showEvidence &&
        (linkedEvidence.length > 0 ? (
          <div className="card__evidence">
            {linkedEvidence.map((item) => (
              <p key={item.id}>
                {item.content ? `“${item.content}” ` : ""}
                <span className="evidence__meta">
                  {item.source_name ? `Via ${item.source_name}` : "Captured by hand"}
                  {item.url && (
                    <>
                      {" · "}
                      <a href={item.url} target="_blank" rel="noopener noreferrer">
                        Source ↗
                      </a>
                    </>
                  )}
                </span>
              </p>
            ))}
          </div>
        ) : (
          <p className="card__evidence">
            {outcome.evidence?.trim() || "No transcript is linked to this outcome yet."}
          </p>
        ))}

      {editing && (
        <form
          className="card__edit"
          onSubmit={(event) => {
            event.preventDefault();
            if (!outcome.id || saving) {
              return;
            }
            setSaving(true);
            void updateOutcome(outcomeId, { importance, satisfaction }).finally(() => {
              setSaving(false);
              setEditing(false);
            });
          }}
        >
          <label className="card__slider" htmlFor={`importance-${outcomeId}`}>
            Importance · {importance.toFixed(1)}
            <input
              id={`importance-${outcomeId}`}
              type="range"
              min={1}
              max={10}
              step={0.1}
              value={importance}
              onChange={(event) => setImportance(Number(event.target.value))}
            />
          </label>
          <label className="card__slider" htmlFor={`satisfaction-${outcomeId}`}>
            Satisfaction · {satisfaction.toFixed(1)}
            <input
              id={`satisfaction-${outcomeId}`}
              type="range"
              min={1}
              max={10}
              step={0.1}
              value={satisfaction}
              onChange={(event) => setSatisfaction(Number(event.target.value))}
            />
          </label>
          <p className="score-preview">
            Opportunity <b>{opportunityScore(importance, satisfaction).toFixed(2)}</b>
          </p>
          <div className="card__edit-actions">
            <button type="submit" className="button button--ghost" disabled={saving}>
              {saving ? "Saving…" : "Save scores"}
            </button>
            <button type="button" className="quiet-action" onClick={() => setEditing(false)}>
              Cancel
            </button>
          </div>
        </form>
      )}

      <div className="card__actions">
        <button
          type="button"
          className="quiet-action"
          aria-label="Copy outcome statement"
          title="Copy the statement"
          onClick={() => {
            if (!navigator.clipboard) {
              pushToast("error", "Could not copy the statement.");
              return;
            }
            void navigator.clipboard
              .writeText(statement)
              .then(() => pushToast("success", "Copied"))
              .catch(() => pushToast("error", "Could not copy the statement."));
          }}
        >
          <CopyIcon size={14} /> Copy
        </button>
        <button
          type="button"
          className="quiet-action"
          aria-expanded={showEvidence}
          title="Inspect customer interview transcripts and evidence line"
          onClick={() => setShowEvidence((prev) => !prev)}
        >
          {showEvidence ? "Hide evidence" : "Evidence"}
        </button>
        <button
          type="button"
          className="quiet-action"
          title="Ask the studio what a bet on this outcome would change"
          onClick={() =>
            ask(
              `Simulate the impact of a bet on ${outcomeId}: "${statement}". ` +
                "What has to be true, and what changes if we ship it?",
            )
          }
        >
          Simulate
        </button>
        {outcome.id && (
          <button
            type="button"
            className="quiet-action"
            aria-expanded={editing}
            onClick={() => setEditing((prev) => !prev)}
          >
            {editing ? "Stop editing" : "Adjust scores"}
          </button>
        )}
        <button
          type="button"
          className="quiet-action"
          aria-expanded={thesisOpen}
          onClick={() => setThesisOpen((prev) => !prev)}
        >
          Save as thesis
        </button>
        <button
          type="button"
          className="quiet-action"
          title="Consult the studio on strategic solutions for this outcome"
          onClick={() => ask(`How should we solve outcome ${outcomeId}: "${statement}"?`)}
        >
          Ask
        </button>
        {outcome.id && (
          <button
            type="button"
            className="quiet-action quiet-action--danger"
            disabled={!outcome.id}
            onClick={() => {
              if (!confirmDelete) {
                setConfirmDelete(true);
                return;
              }
              setConfirmDelete(false);
              void deleteOutcome(outcomeId);
            }}
          >
            {confirmDelete ? "Confirm remove" : "Remove"}
          </button>
        )}
      </div>

      {thesisOpen && (
        <form
          className="card__edit"
          aria-label={`Save ${outcomeId} as an opportunity thesis`}
          onSubmit={(event) => {
            event.preventDefault();
            saveThesis({
              outcome_id: outcomeId,
              job_id: outcome.job_id,
              statement,
              importance: outcome.importance ?? null,
              satisfaction: outcome.satisfaction ?? null,
              opportunity_score: opp ?? null,
              rationale: rationale.trim(),
            });
            setThesisOpen(false);
            setRationale("");
            pushToast("success", "Opportunity thesis saved");
          }}
        >
          <label className="card__slider" htmlFor={`rationale-${outcomeId}`}>
            Why this bet, and what has to be true?
            <textarea
              id={`rationale-${outcomeId}`}
              value={rationale}
              onChange={(event) => setRationale(event.target.value)}
              rows={3}
            />
          </label>
          <div className="card__edit-actions">
            <button type="submit" className="button button--ghost">
              Save thesis
            </button>
            <button
              type="button"
              className="quiet-action"
              onClick={() => setThesisOpen(false)}
            >
              Cancel
            </button>
          </div>
        </form>
      )}
    </article>
  );
}
