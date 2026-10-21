import { useMemo, useState } from "react";

import { isUnderserved } from "../../lib/odi";
import { useStudio } from "../../state/StudioContext";
import { GhostMetrics, GhostOpportunityCards } from "../Skeletons";
import { OutcomeCard } from "./OutcomeCard";

export function OpportunityLandscape() {
  const { canvasState, refreshCanvas } = useStudio();
  const [underservedOnly, setUnderservedOnly] = useState(false);
  const [sorted, setSorted] = useState(false);

  const canvas = canvasState.data;
  const jobs = useMemo(() => canvas?.jobs ?? [], [canvas]);
  const outcomes = useMemo(() => canvas?.outcomes ?? [], [canvas]);
  const isLoading = canvasState.kind === "loading";
  const isEmpty = canvasState.kind === "empty";

  const underservedCount = outcomes.filter((outcome) =>
    isUnderserved(outcome.opportunity_score),
  ).length;

  const visible = useMemo(() => {
    const filtered = underservedOnly
      ? outcomes.filter((outcome) => isUnderserved(outcome.opportunity_score))
      : [...outcomes];
    if (sorted) {
      filtered.sort(
        (a, b) => (b.opportunity_score ?? -Infinity) - (a.opportunity_score ?? -Infinity),
      );
    }
    return filtered;
  }, [outcomes, underservedOnly, sorted]);

  return (
    <section className="fade-in">
      <h2 className="section-title">The Landscape of Human Need</h2>
      <p className="caption">
        Outcomes with Opportunity Scores &gt; 10 indicate underserved market needs and pulse as high-priority innovation targets.
      </p>

      {canvasState.kind === "error" ? (
        <FailurePanel
          error={canvasState.error}
          onRetry={() => void refreshCanvas()}
          retryText="reload"
        />
      ) : canvas?.warnings?.length ? (
        <ul className="canvas-warnings" role="status">
          {canvas.warnings.map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
        </ul>
      ) : isEmpty ? (
        <div className="studio-empty" role="status">
          <p className="studio-empty__title">No opportunities yet</p>
          <p className="studio-empty__body">
            Capture an outcome and the landscape will show what is underserved.
          </p>
        </div>
      ) : isLoading ? (
        <GhostMetrics />
      ) : (
        <div className="metric-grid">
          <div className="studio-metric">
            <div className="studio-metric__label">Active Jobs</div>
            <div className="studio-metric__value">{jobs.length}</div>
          </div>
          <div className="studio-metric">
            <div className="studio-metric__label">Underserved (&gt;10)</div>
            <div className="studio-metric__value">{underservedCount}</div>
            <div className="studio-metric__delta">High Potential</div>
          </div>
          <div className="studio-metric">
            <div className="studio-metric__label">Total Outcomes</div>
            <div className="studio-metric__value">{outcomes.length}</div>
          </div>
        </div>
      )}

      <div style={{ display: "flex", gap: 12, marginBottom: 12, flexWrap: "wrap" }}>
        <label style={{ fontSize: "0.82rem", color: "var(--studio-muted)" }}>
          <input
            type="checkbox"
            checked={sorted}
            onChange={(event) => setSorted(event.target.checked)}
          />{" "}
          Sort by Opportunity Score
        </label>
        <label style={{ fontSize: "0.82rem", color: "var(--studio-muted)" }}>
          <input
            type="checkbox"
            checked={underservedOnly}
            onChange={(event) => setUnderservedOnly(event.target.checked)}
          />{" "}
          Underserved only
        </label>
      </div>

      <hr style={{ borderColor: "var(--studio-border)" }} />

      {canvasLoading && !canvas ? (
        <GhostOpportunityCards />
      ) : visible.length ? (
        visible.map((outcome, index) => (
          <OutcomeCard outcome={outcome} key={outcome.id ?? index} />
        ))
      ) : (
        <p className="caption">No outcomes match the current filter.</p>
      )}
    </section>
  );
}
