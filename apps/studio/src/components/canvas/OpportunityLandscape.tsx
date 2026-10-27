import { useMemo, useState } from "react";

import { formatOpportunityScore, isUnderserved } from "../../lib/odi";
import { useStudio } from "../../state/StudioContext";
import type { Outcome } from "../../types";
import { FailurePanel } from "../FailurePanel";
import { GhostMetrics, GhostOpportunityCards } from "../Skeletons";
import { OutcomeCard } from "./OutcomeCard";

type ViewMode = "matrix" | "cards" | "table";

export function OpportunityLandscape() {
  const { canvasState, deleteThesis, refreshCanvas, theses } = useStudio();
  const [underservedOnly, setUnderservedOnly] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedOutcomeId, setSelectedOutcomeId] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>("matrix");
  const [hoveredOutcome, setHoveredOutcome] = useState<Outcome | null>(null);

  const canvas = canvasState.data;
  const sample = canvas?.source === "seed";
  const jobs = useMemo(() => canvas?.jobs ?? [], [canvas]);
  const outcomes = useMemo(() => canvas?.outcomes ?? [], [canvas]);
  const isLoading = canvasState.kind === "loading";
  const isEmpty = canvasState.kind === "empty";

  const underservedCount = outcomes.filter((outcome) =>
    isUnderserved(outcome.opportunity_score),
  ).length;

  const avgOpportunity = useMemo(() => {
    if (!outcomes.length) return 0;
    const total = outcomes.reduce((acc, o) => acc + (o.opportunity_score ?? 0), 0);
    return (total / outcomes.length).toFixed(1);
  }, [outcomes]);

  const filteredOutcomes = useMemo(() => {
    return outcomes.filter((outcome) => {
      if (underservedOnly && !isUnderserved(outcome.opportunity_score)) {
        return false;
      }
      if (searchQuery.trim()) {
        const query = searchQuery.toLowerCase();
        const stmt = outcome.statement?.toLowerCase() ?? "";
        const id = outcome.id?.toLowerCase() ?? "";
        return stmt.includes(query) || id.includes(query);
      }
      return true;
    });
  }, [outcomes, underservedOnly, searchQuery]);

  const sortedOutcomes = useMemo(() => {
    return [...filteredOutcomes].sort(
      (a, b) => (b.opportunity_score ?? -Infinity) - (a.opportunity_score ?? -Infinity),
    );
  }, [filteredOutcomes]);

  const activeOutcome = useMemo(() => {
    if (selectedOutcomeId) {
      return outcomes.find((o) => o.id === selectedOutcomeId) ?? null;
    }
    return hoveredOutcome || sortedOutcomes[0] || null;
  }, [selectedOutcomeId, outcomes, hoveredOutcome, sortedOutcomes]);

  return (
    <section className="fade-in">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", flexWrap: "wrap", gap: 12 }}>
        <div>
          <p className="section-title" style={{ margin: 0, fontSize: "1.4rem", fontWeight: 700, letterSpacing: "-0.02em" }}>
            Opportunity Landscape
          </p>
          <p className="caption" style={{ marginTop: 4, margin: 0, color: "var(--studio-muted)" }}>
            Interactive 2D Opportunity Matrix mapping Importance vs. Satisfaction. High Opportunity (&gt;10) targets pulse as primary innovation levers.
          </p>
        </div>

        {/* View Mode Switcher */}
        <div style={{ display: "flex", background: "rgba(255, 255, 255, 0.05)", padding: 3, borderRadius: 8, border: "1px solid var(--studio-border)" }}>
          <button
            type="button"
            className={`studio-button ${viewMode === "matrix" ? "studio-button--primary" : ""}`}
            style={{ padding: "4px 12px", fontSize: "0.8rem", borderRadius: 6, border: "none" }}
            onClick={() => setViewMode("matrix")}
          >
            📊 Matrix
          </button>
          <button
            type="button"
            className={`studio-button ${viewMode === "cards" ? "studio-button--primary" : ""}`}
            style={{ padding: "4px 12px", fontSize: "0.8rem", borderRadius: 6, border: "none" }}
            onClick={() => setViewMode("cards")}
          >
            🎴 Visual Cards
          </button>
          <button
            type="button"
            className={`studio-button ${viewMode === "table" ? "studio-button--primary" : ""}`}
            style={{ padding: "4px 12px", fontSize: "0.8rem", borderRadius: 6, border: "none" }}
            onClick={() => setViewMode("table")}
          >
            📋 Table View
          </button>
        </div>
      </div>

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
        <div className="metric-grid" style={{ marginTop: 16, marginBottom: 16 }}>
          <div className="studio-metric">
            <div className="studio-metric__label">Active Job Map Contexts</div>
            <div className="studio-metric__value">{jobs.length}</div>
          </div>
          <div className="studio-metric">
            <div className="studio-metric__label">Underserved Targets (&gt;10)</div>
            <div className="studio-metric__value" style={{ color: "var(--studio-amber)" }}>{underservedCount}</div>
            <div className="studio-metric__delta">High Value Innovation</div>
          </div>
          <div className="studio-metric">
            <div className="studio-metric__label">Total Opportunities Analyzed</div>
            <div className="studio-metric__value">{outcomes.length}</div>
          </div>
          <div className="studio-metric">
            <div className="studio-metric__label">Avg Opportunity Score</div>
            <div className="studio-metric__value">{avgOpportunity}</div>
          </div>
        </div>
      )}

      {/* Control Bar: Search & Filtering */}
      {canvasState.kind === "error" ? null : (
        <div style={{ display: "flex", gap: 12, marginBottom: 16, flexWrap: "wrap", alignItems: "center" }}>
          <div style={{ flex: "1 1 240px" }}>
            <input
              type="text"
              className="studio-input"
              placeholder="Search opportunities / outcomes by statement or ID..."
              value={searchQuery}
              disabled={isLoading}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{ width: "100%" }}
            />
          </div>
          <label style={{ fontSize: "0.85rem", color: "var(--studio-text)", display: "flex", alignItems: "center", gap: 6, cursor: "pointer", userSelect: "none" }}>
            <input
              type="checkbox"
              checked={underservedOnly}
              disabled={isLoading}
              onChange={(event) => setUnderservedOnly(event.target.checked)}
              style={{ accentColor: "var(--studio-indigo)" }}
            />
            Show Underserved Only (&gt;10)
          </label>
          {searchQuery || underservedOnly ? (
            <button
              type="button"
              className="studio-button"
              style={{ fontSize: "0.78rem", padding: "4px 10px" }}
              disabled={isLoading}
              onClick={() => {
                setSearchQuery("");
                setUnderservedOnly(false);
              }}
            >
              Clear Filters
            </button>
          ) : null}
        </div>
      )}

      {isLoading ? (
        <GhostOpportunityCards />
      ) : canvasState.kind === "error" ? null : isEmpty ? (
        <p className="caption" style={{ padding: 24, textAlign: "center", background: "var(--studio-surface)", borderRadius: 8 }}>
          Capture an outcome to see it here.
        </p>
      ) : viewMode === "matrix" ? (
        <OpportunityMatrixView
          outcomes={filteredOutcomes}
          selectedOutcomeId={selectedOutcomeId}
          onSelectOutcome={(id) => setSelectedOutcomeId(selectedOutcomeId === id ? null : id)}
          onHoverOutcome={setHoveredOutcome}
          activeOutcome={activeOutcome}
          sample={sample}
        />
      ) : viewMode === "table" ? (
        <OpportunityTableView
          outcomes={sortedOutcomes}
          selectedOutcomeId={selectedOutcomeId}
          onSelectOutcome={(id) => setSelectedOutcomeId(selectedOutcomeId === id ? null : id)}
        />
      ) : sortedOutcomes.length ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {sortedOutcomes.map((outcome, index) => (
            <OutcomeCard outcome={outcome} sample={sample} key={outcome.id ?? index} />
          ))}
        </div>
      ) : (
        <p className="caption" style={{ padding: 24, textAlign: "center", background: "var(--studio-surface)", borderRadius: 8 }}>
          No opportunities match the current filter criteria.
        </p>
      )}

      {theses.length > 0 && (
        <section aria-label="Saved opportunity theses" style={{ marginTop: 28 }}>
          <h2 className="catchup-title">Opportunity theses</h2>
          <p className="caption">
            Scored bets you saved to share, with the reasoning that makes them reviewable.
          </p>
          <div className="stack" style={{ marginTop: 12 }}>
            {theses.map((thesis) => (
              <article className="card" key={thesis.id} aria-label={`Thesis ${thesis.outcome_id}`}>
                <header className="card__head">
                  <span className="card__id">{thesis.outcome_id}</span>
                  <span className="badge badge--blue">
                    Opportunity {formatOpportunityScore(thesis.opportunity_score)}
                  </span>
                </header>
                <p className="card__statement">{thesis.statement}</p>
                <p className="card__meta">
                  Importance <b>{thesis.importance ?? "—"}</b>
                  <span aria-hidden="true"> · </span>
                  Satisfaction <b>{thesis.satisfaction ?? "—"}</b>
                </p>
                {thesis.rationale ? <p className="card__evidence">{thesis.rationale}</p> : null}
                <div className="card__actions">
                  <button
                    type="button"
                    className="quiet-action quiet-action--danger"
                    onClick={() => deleteThesis(thesis.id)}
                  >
                    Remove thesis
                  </button>
                </div>
              </article>
            ))}
          </div>
        </section>
      )}
    </section>
  );
}

interface MatrixViewProps {
  outcomes: Outcome[];
  selectedOutcomeId: string | null;
  onSelectOutcome: (id: string) => void;
  onHoverOutcome: (outcome: Outcome | null) => void;
  activeOutcome: Outcome | null;
  sample: boolean;
}

function OpportunityMatrixView({
  outcomes,
  selectedOutcomeId,
  onSelectOutcome,
  onHoverOutcome,
  activeOutcome,
  sample,
}: MatrixViewProps) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 320px", gap: 16 }}>
      {/* Interactive 2D Chart */}
      <div
        style={{
          background: "rgba(11, 13, 19, 0.6)",
          border: "1px solid var(--studio-border)",
          borderRadius: 12,
          padding: 16,
          position: "relative",
          display: "flex",
          flexDirection: "column",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8, fontSize: "0.78rem", color: "var(--studio-muted)" }}>
          <span>Y-Axis: Importance (0 - 10)</span>
          <span>X-Axis: Satisfaction (0 - 10)</span>
        </div>

        <div style={{ position: "relative", width: "100%", aspectRatio: "1.4 / 1", minHeight: 320 }}>
          <svg
            viewBox="0 0 500 360"
            style={{ width: "100%", height: "100%", overflow: "visible" }}
          >
            {/* Grid background lines */}
            <defs>
              <linearGradient id="underservedGlow" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="rgba(251, 191, 36, 0.15)" />
                <stop offset="100%" stopColor="rgba(251, 191, 36, 0.02)" />
              </linearGradient>
              <filter id="glowEffect" x="-20%" y="-20%" width="140%" height="140%">
                <feGaussianBlur stdDeviation="3" result="blur" />
                <feComposite in="SourceGraphic" in2="blur" operator="over" />
              </filter>
            </defs>

            {/* Grid lines */}
            {[0, 2, 4, 6, 8, 10].map((val) => {
              const x = (val / 10) * 440 + 40;
              const y = 320 - (val / 10) * 280;
              return (
                <g key={val}>
                  {/* Vertical grid line */}
                  <line x1={x} y1={20} x2={x} y2={320} stroke="rgba(255, 255, 255, 0.05)" strokeDasharray="3,3" />
                  <text x={x} y={338} fill="var(--studio-muted)" fontSize="10" textAnchor="middle">
                    {val}
                  </text>
                  {/* Horizontal grid line */}
                  <line x1={40} y1={y} x2={480} y2={y} stroke="rgba(255, 255, 255, 0.05)" strokeDasharray="3,3" />
                  <text x={30} y={y + 3} fill="var(--studio-muted)" fontSize="10" textAnchor="end">
                    {val}
                  </text>
                </g>
              );
            })}

            {/* Underserved / High Opportunity Region Polygon (Imp + max(Imp - Sat, 0) > 10) */}
            {/* High importance, low satisfaction area top-left */}
            <polygon
              points="40,20 280,20 480,220 480,320 40,320"
              fill="url(#underservedGlow)"
              stroke="rgba(251, 191, 36, 0.2)"
              strokeWidth="1"
              strokeDasharray="4,4"
            />
            <text x={60} y={45} fill="var(--studio-amber)" fontSize="11" fontWeight="600" opacity="0.8">
              ★ Underserved Innovation Zone (Opp Score &gt; 10)
            </text>
            <text x={470} y={310} fill="rgba(255,255,255,0.2)" fontSize="11" textAnchor="end">
              Overserved Zone
            </text>

            {/* Render Outcome Points */}
            {outcomes.map((outcome) => {
              const imp = Math.min(Math.max(outcome.importance ?? 5, 0), 10);
              const sat = Math.min(Math.max(outcome.satisfaction ?? 5, 0), 10);
              const opp = outcome.opportunity_score ?? (imp + Math.max(imp - sat, 0));

              // Map (sat, imp) to SVG space (x: 40..480, y: 320..20)
              const cx = (sat / 10) * 440 + 40;
              const cy = 320 - (imp / 10) * 280;

              const isSelected = selectedOutcomeId === outcome.id;
              const isHovered = activeOutcome?.id === outcome.id;
              const underserved = isUnderserved(opp);

              let nodeColor = underserved ? "#fbbf24" : "var(--studio-indigo)";
              if (opp >= 15) nodeColor = "#f87171";

              return (
                <g
                  key={outcome.id}
                  style={{ cursor: "pointer" }}
                  onClick={() => outcome.id && onSelectOutcome(outcome.id)}
                  onMouseEnter={() => onHoverOutcome(outcome)}
                  onMouseLeave={() => onHoverOutcome(null)}
                >
                  {/* Pulse ring for underserved */}
                  {underserved && (
                    <circle
                      cx={cx}
                      cy={cy}
                      r={isSelected ? 16 : 12}
                      fill="none"
                      stroke={nodeColor}
                      strokeWidth="1.5"
                      opacity="0.4"
                    >
                      <animate
                        attributeName="r"
                        values={isSelected ? "12;18;12" : "8;14;8"}
                        dur="3s"
                        repeatCount="indefinite"
                      />
                      <animate
                        attributeName="opacity"
                        values="0.6;0.1;0.6"
                        dur="3s"
                        repeatCount="indefinite"
                      />
                    </circle>
                  )}

                  {/* Main Node Point */}
                  <circle
                    cx={cx}
                    cy={cy}
                    r={isSelected ? 9 : isHovered ? 8 : 6}
                    fill={nodeColor}
                    stroke="#0b0d13"
                    strokeWidth="2"
                    filter={underserved || isSelected ? "url(#glowEffect)" : undefined}
                  />

                  {/* Node ID Label */}
                  <text
                    x={cx}
                    y={cy - 12}
                    fill={isSelected || isHovered ? "#ffffff" : "var(--studio-muted)"}
                    fontSize={isSelected ? "12" : "10"}
                    fontWeight={isSelected || isHovered ? "700" : "500"}
                    textAnchor="middle"
                  >
                    {outcome.id}
                  </text>
                </g>
              );
            })}
          </svg>
        </div>
      </div>

      {/* Selected / Hovered Details Card Sidebar */}
      <div>
        {activeOutcome ? (
          <div style={{ position: "sticky", top: 16 }}>
            <OutcomeCard outcome={activeOutcome} sample={sample} />
          </div>
        ) : (
          <div
            style={{
              padding: 24,
              borderRadius: 12,
              border: "1px dashed var(--studio-border)",
              textAlign: "center",
              color: "var(--studio-muted)",
              fontSize: "0.88rem",
            }}
          >
            Click or hover over any point in the Matrix to inspect detailed metrics, customer trace evidence, and simulate bet impact.
          </div>
        )}
      </div>
    </div>
  );
}

function OpportunityTableView({
  outcomes,
  selectedOutcomeId,
  onSelectOutcome,
}: {
  outcomes: Outcome[];
  selectedOutcomeId: string | null;
  onSelectOutcome: (id: string) => void;
}) {
  return (
    <div style={{ overflowX: "auto", border: "1px solid var(--studio-border)", borderRadius: 12 }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.88rem", textAlign: "left" }}>
        <thead>
          <tr style={{ background: "rgba(255, 255, 255, 0.03)", borderBottom: "1px solid var(--studio-border)", color: "var(--studio-muted)" }}>
            <th style={{ padding: "10px 14px" }}>ID</th>
            <th style={{ padding: "10px 14px" }}>Desired Outcome Statement</th>
            <th style={{ padding: "10px 14px", textAlign: "right" }}>Importance</th>
            <th style={{ padding: "10px 14px", textAlign: "right" }}>Satisfaction</th>
            <th style={{ padding: "10px 14px", textAlign: "right" }}>Opp. Score</th>
            <th style={{ padding: "10px 14px", textAlign: "center" }}>Status</th>
          </tr>
        </thead>
        <tbody>
          {outcomes.map((outcome, idx) => {
            const opp = outcome.opportunity_score ?? 0;
            const underserved = isUnderserved(opp);
            const isSelected = selectedOutcomeId === outcome.id;

            return (
              <tr
                key={outcome.id ?? idx}
                onClick={() => outcome.id && onSelectOutcome(outcome.id)}
                style={{
                  borderBottom: "1px solid var(--studio-border)",
                  cursor: "pointer",
                  background: isSelected
                    ? "rgba(129, 140, 248, 0.12)"
                    : underserved
                    ? "rgba(251, 191, 36, 0.03)"
                    : "transparent",
                  transition: "background 0.15s ease",
                }}
              >
                <td style={{ padding: "10px 14px", fontWeight: 700, color: "var(--studio-indigo)" }}>
                  {outcome.id}
                </td>
                <td style={{ padding: "10px 14px", color: "var(--studio-text)" }}>
                  {outcome.statement}
                </td>
                <td style={{ padding: "10px 14px", textAlign: "right", fontWeight: 600 }}>
                  {outcome.importance ?? "—"}
                </td>
                <td style={{ padding: "10px 14px", textAlign: "right", fontWeight: 600 }}>
                  {outcome.satisfaction ?? "—"}
                </td>
                <td
                  style={{
                    padding: "10px 14px",
                    textAlign: "right",
                    fontWeight: 800,
                    color: underserved ? "var(--studio-amber)" : "inherit",
                  }}
                >
                  {opp.toFixed(1)}
                </td>
                <td style={{ padding: "10px 14px", textAlign: "center" }}>
                  <span
                    className="studio-pill"
                    style={{
                      background: underserved ? "rgba(251, 191, 36, 0.15)" : "rgba(255,255,255,0.05)",
                      color: underserved ? "var(--studio-amber)" : "var(--studio-muted)",
                      fontSize: "0.72rem",
                    }}
                  >
                    {underserved ? "UNDERSERVED" : "NORMAL"}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
