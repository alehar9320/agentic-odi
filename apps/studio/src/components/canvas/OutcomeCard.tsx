import { isUnderserved, opportunityPill } from "../../lib/odi";
import { useStudio } from "../../state/StudioContext";
import type { Outcome } from "../../types";

export function OutcomeCard({ outcome }: { outcome: Outcome }) {
  const { requestSimulate, sendMessage, pushToast, setActiveTab } = useStudio();

  const opp = outcome.opportunity_score;
  const imp = outcome.importance;
  const sat = outcome.satisfaction;
  const statement = outcome.statement ?? "Untitled Outcome";
  const outcomeId = outcome.id ?? "O";
  const underserved = isUnderserved(opp);
  const pill = opportunityPill(opp);

  return (
    <article
      className={}
      aria-label={}
    >
      <div className="outcome-card__head">
        <span className="outcome-card__id">{outcomeId}</span>
        <span className={}>{pill.label}</span>
      </div>

      <div className="outcome-card__statement">&quot;{statement}&quot;</div>

      <div className="outcome-card__meta">
        <span>Importance: <b>{imp != null ? imp : "—"}/10</b></span>
        <span>Satisfaction: <b>{sat != null ? sat : "—"}/10</b></span>
        <span>Opp Score: <b>{opp != null ? opp.toFixed(1) : "—"}</b></span>
      </div>

      <div className="outcome-card__actions" style={{ marginTop: 12 }}>
        <button
          type="button"
          className="studio-button studio-button--ghost"
          onClick={() =>
            pushToast(
              "info",

            )
          }
        >
          🔍 Trace
        </button>
        <button
          type="button"
          className="studio-button"
          onClick={() => {
            requestSimulate(outcomeId);
            setActiveTab("impact");
            pushToast("success", );
          }}
        >
          ⚡ Simulate
        </button>
        <button
          type="button"
          className="studio-button studio-button--ghost"
          onClick={() => void sendMessage()}
        >
          💬 Ask AI
        </button>
      </div>
    </article>
  );
}
