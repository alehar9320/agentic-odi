import { useMemo, useState } from "react";

import { getRemedies, type Remedy } from "../../domain/Remedies";
import { getSessionEvidence, type SessionEvidence } from "../../domain/Verbatims";
import {
  confidencePill,
  formatAdvances,
  formatOpportunityScore,
  hasScore,
  isUnderserved,
  opportunityPill,
  opportunityScore,
  scoreConfidence,
} from "../../lib/odi";
import { useStudio } from "../../state/StudioContext";
import type { Outcome } from "../../types";
import { CopyIcon } from "../icons";

/**
 * The illustrative results behind a finding, labelled where they are used.
 *
 * Both interfaces in `domain/` have no backend yet (#741). A remedy or a
 * session quote that came from a mock must say so on the control the reader is
 * about to press, not in a note underneath it — an unlabelled "2 ways to fix
 * this" gets quoted onward as if it were analysis. The amber badge is the same
 * one the bundled sample rows use.
 */
export function WaysToFix({ remedies }: { remedies: Remedy[] }) {
  const [open, setOpen] = useState(false);
  const illustrative = remedies.some((remedy) => remedy.source !== "real");

  return (
    <section className="card__support">
      <div className="card__support-head">
        <button
          type="button"
          className="quiet-action"
          aria-expanded={open}
          title="Show the changes that would move this finding"
          onClick={() => setOpen((prev) => !prev)}
        >
          {open ? "Hide" : "Ways to fix this"} ({remedies.length})
        </button>
        {illustrative ? (
          <span
            className="badge badge--amber"
            title="No backend computes remedies yet; these are labelled examples."
          >
            Simulated
          </span>
        ) : null}
      </div>

      {open && (
        <>
          <ul className="card__support-list">
            {remedies.map((remedy) => (
              <li key={remedy.id}>
                <p className="card__support-title">
                  {remedy.title}
                  <span className="badge badge--blue">{remedy.effort}</span>
                  {remedy.source !== "real" ? (
                    <span
                      className="badge badge--amber"
                      title="An example, not a computed recommendation."
                    >
                      Simulated
                    </span>
                  ) : null}
                </p>
                <p className="card__support-rationale">{remedy.rationale}</p>
              </li>
            ))}
          </ul>
          {illustrative ? (
            <p className="ui-caption card__support-note">
              Simulated — no backend computes remedies yet
            </p>
          ) : null}
        </>
      )}
    </section>
  );
}

/**
 * The customer words behind a finding.
 *
 * The count is the honest part: it is the canvas's real evidence count when a
 * provenance says what that is, and it is absent — never estimated — when none
 * does. The quotes themselves say "Simulated" until a session layer exists.
 */
export function CustomerWords({ evidence }: { evidence: SessionEvidence }) {
  const [open, setOpen] = useState(false);
  const illustrative = evidence.basis !== "real";
  const count = evidence.count;
  const label =
    count == null
      ? "View customer quotes & session data"
      : `View customer quotes & session data (${count})`;

  return (
    <section className="card__support">
      <div className="card__support-head">
        <button
          type="button"
          className="quiet-action"
          aria-expanded={open}
          title="Show the customer words recorded against this canvas"
          onClick={() => setOpen((prev) => !prev)}
        >
          {open ? "Hide customer quotes" : label}
        </button>
        {illustrative ? (
          <span
            className="badge badge--amber"
            title="The store has no session or verbatim layer yet; these are labelled examples."
          >
            Simulated
          </span>
        ) : null}
      </div>

      {open && (
        <>
          <ul className="card__support-list">
            {evidence.quotes.map((quote, index) => (
              <li key={`${quote.source_name}-${index}`}>
                <p className="card__evidence">“{quote.content}”</p>
                <p className="card__support-source">
                  {quote.source_name} ({quote.source_kind})
                </p>
              </li>
            ))}
          </ul>
          {illustrative ? (
            <p className="ui-caption card__support-note">
              Simulated — no session layer in this store yet
            </p>
          ) : null}
        </>
      )}
    </section>
  );
}

export function OutcomeCard({
  outcome,
  sample = false,
  startEditing = false,
}: {
  outcome: Outcome;
  sample?: boolean;
  /** Opens the score form on mount or when it flips true, so a caller can send
   * the reader straight to the one control that fixes a missing score. */
  startEditing?: boolean;
}) {
  const { ask, canvasState, deleteOutcome, pushToast, saveThesis, updateOutcome } = useStudio();
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

  const opp = outcome.opportunity_score;
  const statement = outcome.statement ?? "Untitled outcome";
  const outcomeId = outcome.id ?? "O";
  // The finding this card is about, read through the #741 interfaces rather
  // than inline literals; a real backend fills both without a UI change.
  const findings = useMemo(() => ({ kind: "outcome", id: outcomeId }), [outcomeId]);
  const remedies = useMemo(() => getRemedies(findings), [findings]);
  const provenance = canvasState.data?.provenance ?? null;
  const sessionEvidence = useMemo(
    () => getSessionEvidence(findings, provenance),
    [findings, provenance],
  );
  const scored = hasScore(opp);
  const underserved = scored && isUnderserved(opp);
  const pill = scored
    ? opportunityPill(opp)
    : { label: "Not scored — no ratings recorded", variant: "blue" };

  // The interview behind the number, and what stands behind it. A score the
  // reader cannot interrogate is the one thing this card must not present as
  // settled, so the level is derived (verified / partly verified / hypothesis)
  // and the indicator itself is the control that reveals the linked quotes.
  const check = outcome.claim_check ?? null;
  const confidence = scoreConfidence(outcome, linkedEvidence);
  const confidenceBadge = confidencePill(confidence);
  // Sample rows are already badged as not the reader's work; a backing notice
  // belongs to the numbers they are being asked to trust.
  const showConfidence = scored && !sample;

  return (
    <article className={`card${underserved ? " card--hot" : ""}`} aria-label={`Outcome ${outcomeId}`}>
      <header className="card__head">
        <span className="card__id">{outcomeId}</span>
        <span className={`badge badge--${pill.variant}`}>{pill.label}</span>
        {showConfidence && (
          <button
            type="button"
            className={`badge badge--${confidenceBadge.variant} badge--button`}
            aria-expanded={showEvidence}
            title={`${confidence.label} — ${confidence.basis}. Show the evidence behind this score.`}
            onClick={() => setShowEvidence((prev) => !prev)}
          >
            {confidence.label}
          </button>
        )}
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

      <p className="card__advances">{formatAdvances(outcome)}</p>

      <WaysToFix remedies={remedies} />
      <CustomerWords evidence={sessionEvidence} />

      {showConfidence && (
        <div className={`claim-check claim-check--${confidence.level}`}>
          <p className="claim-check__head">{confidence.basis}</p>
          {check ? (
            <ul className="claim-check__list">
              <li className="claim-check__group">Asked</li>
              {(check.asked ?? []).map((question) => (
                <li key={question} className="claim-check__item">
                  {question}
                </li>
              ))}
              <li className="claim-check__group">Answered</li>
              {(check.answers ?? []).map((answer) => (
                <li key={answer} className="claim-check__item">
                  {answer}
                </li>
              ))}
              <li className="claim-check__group">Skipped</li>
              {(check.skips ?? []).map((skip) => (
                <li key={skip.question} className="claim-check__item">
                  {skip.question}
                  <em>{skip.reason}</em>
                </li>
              ))}
            </ul>
          ) : null}
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
