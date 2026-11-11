import { useEffect, useState } from "react";

import {
  fetchExistingSolution,
  fetchOutcomeAlternatives,
  fetchOutcomeHistory,
  fetchOutcomeInterval,
} from "../../api/studioApi";
import {
  existingSolutionLabel,
  formatAdvances,
  formatBandProvenance,
  formatOpportunityScore,
  formatSample,
  hasScore,
  isUnderserved,
  opportunityPill,
  opportunityScore,
} from "../../lib/odi";
import { useStudio } from "../../state/StudioContext";
import type { ExistingSolution, Outcome, OutcomeAlternative, OutcomeInterval } from "../../types";
import { CopyIcon } from "../icons";

export function OutcomeCard({
  outcome,
  sample = false,
  detail = false,
  startEditing = false,
}: {
  outcome: Outcome;
  sample?: boolean;
  detail?: boolean;
  /** Opens the score form on mount or when it flips true, so a caller can send
   * the reader straight to the one control that fixes a missing score. */
  startEditing?: boolean;
}) {
  const { ask, canvasState, deleteOutcome, pushToast, saveThesis, settings, updateOutcome } =
    useStudio();
  // Records captured against this outcome, with their way back to the source.
  const linkedEvidence = (canvasState.data?.evidence ?? []).filter(
    (item) => item.outcome_id === outcome.id,
  );
  const [showEvidence, setShowEvidence] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [editing, setEditing] = useState(startEditing);
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
  // The recorded alternatives and the solution state for the detail card
  // (M2-07.2). A `null` read means it has not resolved, which is a distinct
  // state from "asked and found nothing": a failed read leaves the row absent
  // rather than claiming the outcome is un-inventoried.
  const [alternativesFor, setAlternativesFor] = useState<{
    id: string;
    pairs: OutcomeAlternative[];
    state: ExistingSolution;
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

  useEffect(() => {
    const id = outcome.id;
    if (!detail || !id || sample) return;
    let cancelled = false;
    void Promise.all([
      fetchOutcomeAlternatives(id, settings.mcp_url),
      fetchExistingSolution(id, settings.mcp_url),
    ])
      .then(([pairs, state]) => {
        if (!cancelled) setAlternativesFor({ id, pairs, state });
      })
      .catch(() => {
        // A failed read leaves the row absent: rendering "not yet inventoried"
        // would claim we asked and found nothing, which we did not.
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
  const alternatives =
    detail && !sample && alternativesFor && alternativesFor.id === outcome.id
      ? alternativesFor
      : null;

  const opp = outcome.opportunity_score;
  const statement = outcome.statement ?? "Untitled outcome";
  const scored = hasScore(opp);
  const underserved = scored && isUnderserved(opp);
  const pill = scored
    ? opportunityPill(opp)
    : { label: "Not scored — no ratings recorded", variant: "blue" };

  // The interview behind the number. A score the reader cannot interrogate is the
  // one thing this card must not present as settled, so an unverified score is
  // marked apart and a bare number says plainly that nothing was asked.
  const check = outcome.claim_check ?? null;
  const asked = check?.asked ?? [];
  const answers = check?.answers ?? [];
  const skips = check?.skips ?? [];
  const verified = check?.verified === true;
  // Sample rows are already badged as not the reader's work; a by-hand notice
  // belongs to the numbers they are being asked to trust.
  const bareNumber = scored && check === null && !sample;

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

      {alternatives ? (
        <div className="card__meta" data-testid="outcome-alternatives">
          <span title="What customers use today, and how well it serves them">
            {existingSolutionLabel(alternatives.state)}
          </span>
          {alternatives.pairs.length > 0 ? (
            <ul className="card__alternatives">
              {alternatives.pairs.map(({ alternative, link }) => (
                <li key={alternative.id ?? `${link.outcome_id}-${link.alternative_id}`}>
                  {alternative.name} ({alternative.kind}, adequacy {link.adequacy})
                  {link.usage_n != null ? `, n=${link.usage_n}` : ""}
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}

      <p className="card__advances">{formatAdvances(outcome)}</p>
      {(check || bareNumber) && (
        <div className={`claim-check${verified ? "" : " claim-check--unverified"}`}>
          {check ? (
            <>
              <p className="claim-check__head">
                <b>{verified ? "Verified" : "Unverified"}</b>
                <span aria-hidden="true"> · </span>
                {answers.length} of {asked.length} answered
                {skips.length > 0 && (
                  <>
                    <span aria-hidden="true"> · </span>
                    {skips.length} skipped
                  </>
                )}
              </p>
              <ul className="claim-check__list">
                <li className="claim-check__group">Asked</li>
                {asked.map((question) => (
                  <li key={question} className="claim-check__item">
                    {question}
                  </li>
                ))}
                <li className="claim-check__group">Answered</li>
                {answers.map((answer) => (
                  <li key={answer} className="claim-check__item">
                    {answer}
                  </li>
                ))}
                <li className="claim-check__group">Skipped</li>
                {skips.map((skip) => (
                  <li key={skip.question} className="claim-check__item">
                    {skip.question}
                    <em>{skip.reason}</em>
                  </li>
                ))}
              </ul>
            </>
          ) : (
            <p className="claim-check__head">
              <b>Unverified</b>
              <span aria-hidden="true"> · </span>
              <span>No questions recorded behind this score</span>
            </p>
          )}
        </div>
      )}

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
            Opportunity <b>{formatOpportunityScore(opportunityScore(importance, satisfaction))}</b>
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
