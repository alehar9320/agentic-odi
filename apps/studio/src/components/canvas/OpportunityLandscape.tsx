import { useMemo, useState } from "react";

import { isUnderserved } from "../../lib/odi";
import { useStudio } from "../../state/StudioContext";
import { GhostMetrics, GhostOpportunityCards } from "../Skeletons";
import { OutcomeCard } from "./OutcomeCard";

export function OpportunityLandscape() {
  const { canvas, canvasLoading } = useStudio();
  const [underservedOnly, setUnderservedOnly] = useState(false);
  const [sorted, setSorted] = useState(false);

  const jobs = useMemo(() => canvas?.jobs ?? [], [canvas]);
  const outcomes = useMemo(() => canvas?.outcomes ?? [], [canvas]);

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
        Outcomes with Opportunity Scores &gt; 10 pulse as urgent innovation targets.
      </p>

      {canvasLoading && !canvas ? (
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

      <div style={{ display: "flex", gap: 16, marginBottom: 16, flexWrap: "wrap", alignItems: "center" }}>
        <label style={{ fontSize: "0.85rem", color: "var(--studio-text)", cursor: "pointer", display: "inline-flex", alignItems: "center", gap: 6, minHeight: 44 }}>
          <input
            type="checkbox"
            checked={sorted}
            onChange={(event) => setSorted(event.target.checked)}
            style={{ width: 18, height: 18, accentColor: "var(--studio-indigo-strong)" }}
          />{" "}
          Sort by Score
        </label>
        <label style={{ fontSize: "0.85rem", color: "var(--studio-text)", cursor: "pointer", display: "inline-flex", alignItems: "center", gap: 6, minHeight: 44 }}>
          <input
            type="checkbox"
            checked={underservedOnly}
            onChange={(event) => setUnderservedOnly(event.target.checked)}
            style={{ width: 18, height: 18, accentColor: "var(--studio-indigo-strong)" }}
          />{" "}
          Underserved only (&gt;10)
        </label>
      </div>

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
