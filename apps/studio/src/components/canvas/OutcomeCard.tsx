import { isUnderserved, opportunityPill } from "../../lib/odi";
import { useStudio } from "../../state/StudioContext";
import type { Outcome } from "../../types";

export function OutcomeCard({ outcome }: { outcome: Outcome }) {
  const { requestSimulate, sendMessage, pushToast } = useStudio();

  const opp = outcome.opportunity_score;
  const imp = outcome.importance;
  const sat = outcome.satisfaction;
  const statement = outcome.statement ?? "Untitled Outcome";
  const outcomeId = outcome.id ?? "O";
  const underserved = isUnderserved(opp);
  const pill = opportunityPill(opp);

  return (
    <>
      <article
        className={`outcome-card fade-in${underserved ? " pulsing-card" : ""}`}
        aria-label={`Outcome ${outcomeId}`}
      >
        <div className="outcome-card__head">
          <span className="outcome-card__id">{outcomeId}</span>
          <span className={`studio-pill pill-${pill.variant}`}>{pill.label}</span>
        </div>
        <div className="outcome-card__statement">&quot;{statement}&quot;</div>
        <div className="outcome-card__meta">
          Importance: <b>{imp != null ? imp : "—"}/10</b> &nbsp;|&nbsp; Current Satisfaction:{" "}
          <b>{sat != null ? sat : "—"}/10</b> &nbsp;|&nbsp; Formula: <i>Imp + max(Imp - Sat, 0)</i>
        </div>
      </article>

      <div className="outcome-card__actions">
        <button
          type="button"
          className="studio-button"
          title="Inspect customer interview transcripts and evidence line"
          onClick={() =>
            pushToast(
              "info",
              `Customer Evidence Lineage:\n\n${outcome.evidence ?? "No transcript linked."}`,
            )
          }
        >
          🔍 Inspect Trace ({outcomeId})
        </button>
        <button
          type="button"
          className="studio-button"
          title="Simulate time savings and impact in simulator"
          onClick={() => {
            requestSimulate(outcomeId);
            pushToast("success", `Outcome ${outcomeId} loaded into WYSIWYG Impact Simulator.`);
          }}
        >
          ⚡ Simulate Bet ({outcomeId})
        </button>
        <button
          type="button"
          className="studio-button"
          title="Consult AI Copilot on strategic solutions for this outcome"
          onClick={() => void sendMessage(`How should we solve outcome ${outcomeId}: '${statement}'?`)}
        >
          💬 Ask Agent ({outcomeId})
        </button>
      </div>
    </>
  );
}
