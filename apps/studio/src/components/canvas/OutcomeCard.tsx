import { useState } from "react";

import { formatOpportunityScore, isUnderserved, opportunityPill } from "../../lib/odi";
import { useStudio } from "../../state/StudioContext";
import type { Outcome } from "../../types";

export function OutcomeCard({ outcome }: { outcome: Outcome }) {
  const { requestSimulate, sendMessage, closePanel } = useStudio();
  const [showEvidence, setShowEvidence] = useState(false);

  const opp = outcome.opportunity_score;
  const statement = outcome.statement ?? "Untitled outcome";
  const outcomeId = outcome.id ?? "O";
  const underserved = isUnderserved(opp);
  const pill = opportunityPill(opp);

  return (
    <article className={`card${underserved ? " card--hot" : ""}`} aria-label={`Outcome ${outcomeId}`}>
      <header className="card__head">
        <span className="card__id">{outcomeId}</span>
        <span className={`badge badge--${pill.variant}`}>{pill.label}</span>
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
        <p className="card__evidence">
          {outcome.evidence?.trim() || "No transcript is linked to this outcome yet."}
        </p>
      )}

      <div className="card__actions">
        <button
          type="button"
          className="quiet-action"
          aria-expanded={showEvidence}
          onClick={() => setShowEvidence((prev) => !prev)}
        >
          {showEvidence ? "Hide evidence" : "Evidence"}
        </button>
        <button type="button" className="quiet-action" onClick={() => requestSimulate(outcomeId)}>
          Simulate
        </button>
        <button
          type="button"
          className="quiet-action"
          onClick={() => {
            closePanel();
            void sendMessage(`How should we solve outcome ${outcomeId}: "${statement}"?`);
          }}
        >
          Ask
        </button>
      </div>
    </article>
  );
}
