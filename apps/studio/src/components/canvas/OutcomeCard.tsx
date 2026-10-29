import { useState } from "react";

import {
  formatOpportunityScore,
  isUnderserved,
  opportunityPill,
  opportunityScore,
} from "../../lib/odi";
import { useStudio } from "../../state/StudioContext";
import type { Evidence, Outcome } from "../../types";
import { CopyIcon } from "../icons";

export function OutcomeCard({ outcome, sample = false }: { outcome: Outcome; sample?: boolean }) {
  const { ask, deleteOutcome, fetchOutcomeEvidence, pushToast, saveThesis, updateOutcome } =
    useStudio();
  const [showEvidence, setShowEvidence] = useState(false);
  const [evidence, setEvidence] = useState<Evidence[] | null>(null);
  const [evidenceError, setEvidenceError] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [editing, setEditing] = useState(false);
  const [thesisOpen, setThesisOpen] = useState(false);
  const [rationale, setRationale] = useState("");
  const [importance, setImportance] = useState(outcome.importance ?? 5);
  const [satisfaction, setSatisfaction] = useState(outcome.satisfaction ?? 5);
  const [saving, setSaving] = useState(false);

  const opp = outcome.opportunity_score;
  const statement = outcome.statement ?? "Untitled outcome";
  const outcomeId = outcome.id ?? "O";
  const underserved = isUnderserved(opp);
  const pill = opportunityPill(opp);

  const toggleEvidence = () => {
    const next = !showEvidence;
    setShowEvidence(next);
    if (!next || !outcome.id || evidence !== null) {
      return;
    }
    // Read the count from the store on open, never from a stored counter, so
    // it cannot drift from the records it claims to summarise.
    void fetchOutcomeEvidence(outcome.id)
      .then((items) => setEvidence(items))
      .catch(() => setEvidenceError(true));
  };

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
      </p>

      {showEvidence && (
        <div className="card__evidence">
          {evidenceError ? (
            <p>Could not load the evidence behind this outcome.</p>
          ) : evidence === null ? (
            <p>Loading evidence…</p>
          ) : evidence.length === 0 ? (
            <p>No transcript is linked to this outcome yet.</p>
          ) : (
            <>
              <p>
                {evidence.length} source{evidence.length === 1 ? "" : "s"} behind this number
              </p>
              <ul className="card__evidence-list">
                {evidence.map((item) => (
                  <li key={item.id}>
                    <span className="card__evidence-source">
                      {item.source_name ?? item.source_kind ?? "Source"}
                    </span>
                    <blockquote>{item.content ?? ""}</blockquote>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}

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
          onClick={toggleEvidence}
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
