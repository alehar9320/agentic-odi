import { useEffect, useMemo, useRef, useState } from "react";

import { asStudioError, fetchOutcomeSearch, fetchThemes } from "../../api/studioApi";
import { JOB_STAGES } from "../../domain/jobStages";
import {
  canvasHasRecords,
  canvasStatus,
  isSimulatedCanvas,
  savedCopyCaption,
} from "../../lib/canvasProvenance";
import {
  formatOpportunityScore,
  isUnderserved,
  UNDERSERVED_THRESHOLD,
} from "../../lib/odi";
import { useStudio } from "../../state/StudioContext";
import type { Outcome, OutcomeSearch, StudioError, Theme } from "../../types";
import { FailurePanel } from "../FailurePanel";
import { GhostMetrics, GhostOpportunityCards } from "../Skeletons";
import { OutcomeCard } from "./OutcomeCard";

type ViewMode = "matrix" | "cards" | "table";

/**
 * The matrix plots one DOM node per outcome (a point, a control, and an
 * accessible list entry). At study scale that measured ~590ms and ~9,000 nodes
 * on the first interactive render, so the plot defers its tail: the first
 * screen plots the highest-opportunity outcomes and the rest are one control
 * away. Small boards are unaffected — every outcome is below the limit.
 */
const MATRIX_POINT_LIMIT = 200;

/** How many narrowed rows the store hands back at a time. */
const SEARCH_PAGE_SIZE = 50;

/** The narrowing the person has asked the store for. Absent means not filtered. */
interface Narrowing {
  text?: string;
  stage?: string;
  themeIds?: string[];
  confidence?: string;
  minScore?: number;
  maxScore?: number;
}

type SearchStatus = "loading" | "ready" | "error";

const BLANK_NARROWING: Narrowing = {};

function isNarrowing(query: Narrowing): boolean {
  return Boolean(
    query.text ||
      query.stage ||
      query.confidence ||
      query.themeIds?.length ||
      query.minScore !== undefined ||
      query.maxScore !== undefined,
  );
}

/** The stage's own words, without the ordinal the generated catalog numbers it with. */
function stageLabel(stage: string): string {
  const known = JOB_STAGES.find((entry) => entry.id === stage);
  return known ? known.name.replace(/^\d+\.\s*/, "") : stage;
}

export function OpportunityLandscape() {
  const {
    canvasState,
    canvasCached,
    deleteThesis,
    openPanel,
    refreshCanvas,
    settings,
    theses,
    focusedSubject,
    focusSubject,
  } = useStudio();
  const [selectedOutcomeId, setSelectedOutcomeId] = useState<string | null>(
    focusedSubject?.kind === "outcome" ? focusedSubject.id : null,
  );
  const [viewMode, setViewMode] = useState<ViewMode>("matrix");
  const [hoveredOutcome, setHoveredOutcome] = useState<Outcome | null>(null);
  const [draft, setDraft] = useState({ text: "", minScore: "", maxScore: "" });
  const [narrowing, setNarrowing] = useState<Narrowing>(BLANK_NARROWING);
  const [offset, setOffset] = useState(0);
  // The board starts asking as soon as it can, so the first status is loading;
  // only an action that re-asks sets it, because an effect may not set state
  // about its own run.
  const [status, setStatus] = useState<SearchStatus>("loading");
  const [result, setResult] = useState<OutcomeSearch | null>(null);
  const [searchError, setSearchError] = useState<StudioError | null>(null);
  const [themes, setThemes] = useState<Theme[]>([]);
  const [retryNonce, setRetryNonce] = useState(0);
  /** Only the newest answer may draw the board; a late one is dropped here. */
  const requestId = useRef(0);

  const canvas = canvasState.data;
  const sample = isSimulatedCanvas(canvas);
  const jobs = useMemo(() => canvas?.jobs ?? [], [canvas]);
  const outcomes = useMemo(() => canvas?.outcomes ?? [], [canvas]);
  const evidence = useMemo(() => canvas?.evidence ?? [], [canvas]);
  const isLoading = canvasState.kind === "loading";
  const isEmpty = canvasState.kind === "empty";
  const provenance = canvasStatus(canvas);
  const hasRecords = canvasHasRecords(canvas);
  const isFailed = canvasState.kind === "error";
  const hasWarnings = Boolean(canvas?.warnings?.length);
  // The board is drawn whenever real data is on screen and nothing else owns the
  // space: not a failure, not the seed warning strip, not a genuinely empty
  // store, and not a cold load that has nothing cached to draw.
  const showBoard = !isFailed && !hasWarnings && !isEmpty && !(isLoading && !hasRecords);
  // Draw the saved copy rather than a skeleton while the sidecar answers, and
  // say when it was saved. A warm reload with live data draws it too but gets
  // no caption, because that data is not a saved copy.
  const savedCaption = canvasCached && hasRecords ? savedCopyCaption(canvas) : null;

  // Narrowing asks the store, so it needs one to ask: the demo board is a
  // fixture the sidecar handed over, and an empty or failed canvas has nothing
  // to narrow. A canvas read straight from the sidecar's own store counts —
  // the query runs there whatever transport brought the board here.
  const canNarrow = !isFailed && !sample && hasRecords;
  const narrowed = isNarrowing(narrowing);
  // A canvas that came back with a new generation has new counts in it.
  const canvasStamp = canvas?.provenance?.generated_at ?? null;

  useEffect(() => {
    if (!canNarrow) {
      return;
    }
    const id = requestId.current + 1;
    requestId.current = id;
    fetchOutcomeSearch(settings.mcp_url, { ...narrowing, limit: SEARCH_PAGE_SIZE, offset })
      .then((response) => {
        if (requestId.current !== id) {
          return;
        }
        setResult(response);
        setSearchError(null);
        setStatus("ready");
      })
      .catch((error: unknown) => {
        if (requestId.current !== id) {
          return;
        }
        setSearchError(asStudioError(error));
        setStatus("error");
      });
  }, [canNarrow, narrowing, offset, canvasStamp, settings.mcp_url, retryNonce]);

  /** Theme names come from the theme list; the facet row only labels what it is given. */
  useEffect(() => {
    if (!canNarrow) {
      return;
    }
    let active = true;
    fetchThemes(settings.mcp_url)
      .then((list) => {
        if (active) {
          setThemes(list);
        }
      })
      .catch(() => {
        // A chip that says "t-1" instead of a name is still the right filter.
      });
    return () => {
      active = false;
    };
  }, [canNarrow, settings.mcp_url]);

  const underservedCount = outcomes.filter((outcome) =>
    isUnderserved(outcome.opportunity_score),
  ).length;

  // Deduplicated demand: distinct customer quotes linked to an outcome. Because
  // repeat imports of the same quote collapse to a single evidence record,
  // counting distinct linked evidence never double-counts demand.
  const linkedQuotes = useMemo(() => {
    const ids = new Set<string>();
    for (const item of evidence) {
      if (item.outcome_id) {
        ids.add(item.id);
      }
    }
    return ids.size;
  }, [evidence]);

  const avgOpportunity = useMemo(() => {
    const total = outcomes.reduce((acc, o) => acc + (o.opportunity_score ?? 0), 0);
    return formatOpportunityScore(outcomes.length ? total / outcomes.length : null);
  }, [outcomes]);

  /**
   * Who owns the rows. A narrowed board is the store's page, in the store's
   * order — re-sorting it here would be a second ordering that can disagree
   * with the pager beside it. An unnarrowed board is the whole library, which
   * is ordered by opportunity as it always was.
   *
   * One rule for every score on this canvas: compare the stored number, display
   * the rounded one. Two outcomes that both print "13.0" still have an order.
   */
  const rows = useMemo(() => {
    if (narrowed) {
      return status === "ready" && result ? result.items : [];
    }
    return [...outcomes].sort(
      (a, b) => (b.opportunity_score ?? -Infinity) - (a.opportunity_score ?? -Infinity),
    );
  }, [narrowed, status, result, outcomes]);

  const page = Math.floor(offset / SEARCH_PAGE_SIZE) + 1;
  const pages =
    narrowed && result ? Math.max(1, Math.ceil(result.total / SEARCH_PAGE_SIZE)) : 1;

  function submitDraft(event: React.FormEvent) {
    event.preventDefault();
    setStatus("loading");
    setNarrowing({
      ...narrowing,
      text: draft.text.trim() || undefined,
      minScore: draft.minScore === "" ? undefined : Number(draft.minScore),
      maxScore: draft.maxScore === "" ? undefined : Number(draft.maxScore),
    });
    setOffset(0);
  }

  function ask(next: Narrowing) {
    setStatus("loading");
    setNarrowing(next);
    setOffset(0);
  }

  function askPage(nextOffset: number) {
    setStatus("loading");
    setOffset(nextOffset);
  }

  function toggleFacet<K extends "stage" | "confidence">(key: K, value: NonNullable<Narrowing[K]>) {
    ask({ ...narrowing, [key]: narrowing[key] === value ? undefined : value });
  }

  function toggleTheme(themeId: string) {
    const current = narrowing.themeIds ?? [];
    const next = current.includes(themeId)
      ? current.filter((id) => id !== themeId)
      : [...current, themeId];
    ask({ ...narrowing, themeIds: next.length ? next : undefined });
  }

  function clearDimension(key: "text" | "stage" | "confidence") {
    if (key === "text") {
      setDraft((current) => ({ ...current, text: "" }));
    }
    ask({ ...narrowing, [key]: undefined });
  }

  /** The band is two fields and one filter, so it clears as one. */
  function clearBand() {
    setDraft((current) => ({ ...current, minScore: "", maxScore: "" }));
    ask({ ...narrowing, minScore: undefined, maxScore: undefined });
  }

  function clearAll() {
    setDraft({ text: "", minScore: "", maxScore: "" });
    ask(BLANK_NARROWING);
  }

  const activeFilters: { dimension: string; label: string; onRemove: () => void }[] = [];
  if (narrowing.text) {
    activeFilters.push({
      dimension: "text",
      label: `text “${narrowing.text}”`,
      onRemove: () => clearDimension("text"),
    });
  }
  if (narrowing.stage) {
    activeFilters.push({
      dimension: "stage",
      label: `stage ${stageLabel(narrowing.stage)}`,
      onRemove: () => clearDimension("stage"),
    });
  }
  for (const themeId of narrowing.themeIds ?? []) {
    const theme = themes.find((entry) => entry.id === themeId);
    activeFilters.push({
      dimension: "theme",
      label: `theme ${theme?.name ?? themeId}`,
      onRemove: () => toggleTheme(themeId),
    });
  }
  if (narrowing.confidence) {
    activeFilters.push({
      dimension: "confidence",
      label: narrowing.confidence,
      onRemove: () => clearDimension("confidence"),
    });
  }
  if (narrowing.minScore !== undefined || narrowing.maxScore !== undefined) {
    activeFilters.push({
      dimension: "score",
      label: `score ${narrowing.minScore ?? "any"} to ${narrowing.maxScore ?? "any"}`,
      onRemove: clearBand,
    });
  }

  function toggleOutcome(id: string) {
    const next = selectedOutcomeId === id ? null : id;
    setSelectedOutcomeId(next);
    if (next) {
      focusSubject("outcome", next);
    }
  }

  const activeOutcome = useMemo(() => {
    if (selectedOutcomeId) {
      return outcomes.find((o) => o.id === selectedOutcomeId) ?? null;
    }
    return hoveredOutcome || rows[0] || null;
  }, [selectedOutcomeId, outcomes, hoveredOutcome, rows]);

  const zeroMatches = narrowed && status === "ready" && result?.total === 0;

  return (
    <section className="fade-in">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", flexWrap: "wrap", gap: 12 }}>
        <div>
          <p className="section-title" style={{ margin: 0, fontSize: "1.4rem", fontWeight: 700, letterSpacing: "-0.02em" }}>
            Opportunity Landscape
          </p>
          <p className="caption" style={{ marginTop: 4, margin: 0, color: "var(--studio-muted)" }}>
            Interactive 2D Opportunity Matrix mapping Importance vs. Satisfaction. Scores above 10 mark underserved market needs and pulse as primary innovation levers.
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

      {provenance ? (
        <p className="canvas-provenance" role="status">
          <strong>Demo data.</strong> Nothing here comes from your research.{" "}
          <button
            type="button"
            className="quiet-action"
            onClick={() => openPanel("settings")}
          >
            Connect a data source
          </button>
        </p>
      ) : null}

      {savedCaption && showBoard ? (
        <p className="canvas-saved" role="status">
          {savedCaption}
        </p>
      ) : null}

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
          <p className="studio-empty__title">No saved copy on this device</p>
          <p className="studio-empty__body">
            Capture an outcome and the landscape will show what is underserved.
          </p>
          <button
            type="button"
            className="button button--ghost"
            onClick={() => openPanel("capture")}
          >
            Capture an outcome
          </button>
        </div>
      ) : isLoading && !hasRecords ? (
        <GhostMetrics />
      ) : (
        <div className="metric-grid" style={{ marginTop: 16, marginBottom: 16 }}>
          <div className="studio-metric">
            <div className="studio-metric__label">Active Job Map Contexts</div>
            <div className="studio-metric__value">{jobs.length}</div>
          </div>
          <div className="studio-metric">
            <div className="studio-metric__label">{`Underserved Targets (>${UNDERSERVED_THRESHOLD})`}</div>
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
          <div className="studio-metric">
            <div className="studio-metric__label">Unique Customer Quotes</div>
            <div className="studio-metric__value">{linkedQuotes}</div>
            <div className="studio-metric__delta">Deduplicated demand</div>
          </div>
        </div>
      )}

      {/* Narrowing: the field, the band, and the facet row all ask the store. */}
      {canvasState.kind === "error" ? null : (
        <div style={{ marginBottom: 16 }}>
          <form
            role="search"
            onSubmit={submitDraft}
            style={{ display: "flex", gap: 12, marginBottom: 8, flexWrap: "wrap", alignItems: "flex-end" }}
          >
            <div style={{ flex: "1 1 240px" }}>
              <label className="sr-only" htmlFor="opportunity-search">
                Search outcomes
              </label>
              <input
                id="opportunity-search"
                type="text"
                className="studio-input"
                placeholder="Search statements, theme names, and evidence…"
                value={draft.text}
                disabled={!canNarrow}
                onChange={(event) => setDraft({ ...draft, text: event.target.value })}
                style={{ width: "100%" }}
              />
            </div>
            <label style={{ fontSize: "0.8rem", color: "var(--studio-muted)", display: "flex", flexDirection: "column", gap: 4 }}>
              Minimum score
              <input
                type="number"
                className="studio-input"
                style={{ width: 120 }}
                value={draft.minScore}
                disabled={!canNarrow}
                onChange={(event) => setDraft({ ...draft, minScore: event.target.value })}
              />
            </label>
            <label style={{ fontSize: "0.8rem", color: "var(--studio-muted)", display: "flex", flexDirection: "column", gap: 4 }}>
              Maximum score
              <input
                type="number"
                className="studio-input"
                style={{ width: 120 }}
                value={draft.maxScore}
                disabled={!canNarrow}
                onChange={(event) => setDraft({ ...draft, maxScore: event.target.value })}
              />
            </label>
            <button type="submit" className="studio-button" disabled={!canNarrow}>
              Search
            </button>
          </form>

          {sample ? (
            <p className="caption" role="status">
              Narrowing asks the store, and this demo board is not in it.
            </p>
          ) : null}

          {status === "error" && searchError ? (
            <FailurePanel
              error={searchError}
              onRetry={() => {
                setStatus("loading");
                setRetryNonce((nonce) => nonce + 1);
              }}
              retryText="retry the search"
            />
          ) : canNarrow && result ? (
            <>
              <div style={{ display: "flex", gap: 16, flexWrap: "wrap", alignItems: "flex-start", marginTop: 8 }}>
                <FacetGroup
                  title="Job stage"
                  entries={Object.entries(result.facets.stage).map(([value, count]) => ({
                    key: value,
                    label: stageLabel(value),
                    count,
                  }))}
                  selected={narrowing.stage ? [narrowing.stage] : []}
                  onToggle={(key) => toggleFacet("stage", key)}
                />
                <FacetGroup
                  title="Theme"
                  entries={Object.entries(result.facets.theme).map(([id, count]) => ({
                    key: id,
                    label: themes.find((theme) => theme.id === id)?.name ?? id,
                    count,
                  }))}
                  selected={narrowing.themeIds ?? []}
                  onToggle={toggleTheme}
                />
                <FacetGroup
                  title="Score recorded"
                  entries={Object.entries(result.facets.confidence).map(([level, count]) => ({
                    key: level,
                    label: level.charAt(0).toUpperCase() + level.slice(1),
                    count,
                  }))}
                  selected={narrowing.confidence ? [narrowing.confidence] : []}
                  onToggle={(key) => toggleFacet("confidence", key)}
                />
              </div>
              <p className="caption" style={{ marginTop: 8 }} role="status">
                {narrowed
                  ? `${result.total} outcome${result.total === 1 ? "" : "s"} match${
                      result.total === 1 ? "es" : ""
                    } these filters`
                  : `All ${result.total} outcomes in the library`}
              </p>
            </>
          ) : null}

          {activeFilters.length ? (
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", marginTop: 8 }}>
              {activeFilters.map((filter) => (
                <button
                  type="button"
                  key={`${filter.dimension}:${filter.label}`}
                  className="studio-pill"
                  style={{ fontSize: "0.75rem" }}
                  aria-label={`Remove ${filter.dimension} filter`}
                  onClick={filter.onRemove}
                >
                  {filter.label} ✕
                </button>
              ))}
              <button
                type="button"
                className="quiet-action"
                style={{ fontSize: "0.78rem" }}
                onClick={clearAll}
              >
                Clear filters
              </button>
            </div>
          ) : null}

          {narrowed && status !== "error" && result && pages > 1 ? (
            <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 8 }}>
              <button
                type="button"
                className="studio-button"
                style={{ fontSize: "0.78rem", padding: "4px 10px" }}
                disabled={offset === 0}
                onClick={() => askPage(Math.max(0, offset - SEARCH_PAGE_SIZE))}
              >
                Previous page
              </button>
              <button
                type="button"
                className="studio-button"
                style={{ fontSize: "0.78rem", padding: "4px 10px" }}
                disabled={page >= pages}
                onClick={() => askPage(offset + SEARCH_PAGE_SIZE)}
              >
                Next page
              </button>
              <p
                className="caption"
                role="status"
                aria-label={`Page ${page} of ${pages}`}
                style={{ margin: 0 }}
              >
                Page {page} of {pages}
              </p>
            </div>
          ) : null}
        </div>
      )}

      {canvasState.kind === "error" ? null : isLoading && !hasRecords ? (
        <GhostOpportunityCards />
      ) : isEmpty ? (
        <p className="caption" style={{ padding: 24, textAlign: "center", background: "var(--studio-surface)", borderRadius: 8 }}>
          Capture an outcome to see it here.
        </p>
      ) : narrowed && status === "loading" ? (
        <>
          <p
            className="caption"
            role="status"
            aria-label="Searching the library"
            style={{ padding: 24, textAlign: "center" }}
          >
            Searching the library…
          </p>
          <GhostOpportunityCards />
        </>
      ) : narrowed && status === "error" ? null : zeroMatches ? (
        <div className="studio-empty" role="status">
          <p className="studio-empty__title">Nothing matches these filters</p>
          <p className="studio-empty__body">
            Clear filters above, or widen one — a filter that excludes everything is still an answer.
          </p>
        </div>
      ) : viewMode === "matrix" ? (
        <OpportunityMatrixView
          outcomes={rows}
          selectedOutcomeId={selectedOutcomeId}
          onSelectOutcome={toggleOutcome}
          onHoverOutcome={setHoveredOutcome}
          activeOutcome={activeOutcome}
          sample={sample}
        />
      ) : viewMode === "table" ? (
        <OpportunityTableView
          outcomes={rows}
          selectedOutcomeId={selectedOutcomeId}
          onSelectOutcome={toggleOutcome}
        />
      ) : rows.length ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {rows.map((outcome, index) => (
            <OutcomeCard outcome={outcome} sample={sample} key={outcome.id ?? index} />
          ))}
        </div>
      ) : (
        <p className="caption" style={{ padding: 24, textAlign: "center", background: "var(--studio-surface)", borderRadius: 8 }}>
          Nothing matches these filters.
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

interface FacetEntry {
  key: string;
  label: string;
  count: number;
}

/**
 * One dimension of the facet row. The counts are the sidecar's own — the same
 * query with this dimension removed — so a chip that says 7 means the store
 * found 7, not that this page holds 7. A bucket with nothing in it stays
 * visible and unreachable rather than vanishing after the last click.
 */
function FacetGroup({
  title,
  entries,
  selected,
  onToggle,
}: {
  title: string;
  entries: FacetEntry[];
  selected: string[];
  onToggle: (key: string) => void;
}) {
  if (!entries.length) {
    return null;
  }
  return (
    <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
      <span className="caption" style={{ color: "var(--studio-muted)", fontSize: "0.75rem" }}>
        {title}
      </span>
      {entries.map((entry) => {
        const isActive = selected.includes(entry.key);
        const reachable = entry.count > 0 || isActive;
        return (
          <button
            key={entry.key}
            type="button"
            className="studio-pill"
            style={{
              fontSize: "0.75rem",
              background: isActive ? "rgba(129, 140, 248, 0.18)" : "rgba(255, 255, 255, 0.05)",
              color: isActive ? "var(--studio-indigo)" : "var(--studio-muted)",
              border: "1px solid var(--studio-border)",
              cursor: reachable ? "pointer" : "not-allowed",
              opacity: reachable ? 1 : 0.5,
            }}
            disabled={!reachable}
            aria-pressed={isActive}
            onClick={() => onToggle(entry.key)}
          >
            {entry.label} {entry.count}
          </button>
        );
      })}
    </div>
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

interface PlottedOutcome {
  outcome: Outcome;
  importance: number;
  satisfaction: number;
  score: number;
  underserved: boolean;
  cx: number;
  cy: number;
}

function OpportunityMatrixView({
  outcomes,
  selectedOutcomeId,
  onSelectOutcome,
  onHoverOutcome,
  activeOutcome,
  sample,
}: MatrixViewProps) {
  const [focusedId, setFocusedId] = useState<string | null>(null);
  const [showAll, setShowAll] = useState(false);
  const nodeRefs = useRef(new Map<string, HTMLButtonElement>());

  const plotted: PlottedOutcome[] = outcomes.map((outcome) => {
    const importance = Math.min(Math.max(outcome.importance ?? 5, 0), 10);
    const satisfaction = Math.min(Math.max(outcome.satisfaction ?? 5, 0), 10);
    const score = outcome.opportunity_score ?? importance + Math.max(importance - satisfaction, 0);
    return {
      outcome,
      importance,
      satisfaction,
      score,
      underserved: isUnderserved(score),
      // Map (satisfaction, importance) into the 500x360 viewBox.
      cx: (satisfaction / 10) * 440 + 40,
      cy: 320 - (importance / 10) * 280,
    };
  });

  // Above the fold: the highest-opportunity outcomes, which is what the
  // landscape exists to show. The tail is one click away rather than in the
  // first render.
  const capped = !showAll && plotted.length > MATRIX_POINT_LIMIT;
  const rendered = capped
    ? [...plotted].sort((a, b) => b.score - a.score).slice(0, MATRIX_POINT_LIMIT)
    : plotted;

  const underservedCount = plotted.filter((plot) => plot.underserved).length;
  const importances = plotted.map((plot) => plot.importance);
  const minImportance = importances.length ? Math.min(...importances) : 0;
  const maxImportance = importances.length ? Math.max(...importances) : 0;
  const summary = `${plotted.length} outcomes, ${underservedCount} of them underserved, spanning importance ${minImportance} to ${maxImportance}.`;

  // One tab stop for the whole plot; the arrow keys carry focus from there.
  const rovingId =
    focusedId && rendered.some((plot) => plot.outcome.id === focusedId)
      ? focusedId
      : (rendered[0]?.outcome.id ?? null);

  function focusInDirection(from: PlottedOutcome, key: string) {
    const step: Record<string, [number, number] | undefined> = {
      ArrowRight: [1, 0],
      ArrowLeft: [-1, 0],
      ArrowUp: [0, -1],
      ArrowDown: [0, 1],
    };
    const direction = step[key];
    if (!direction) {
      return;
    }
    let nearest: { id: string; distance: number } | null = null;
    for (const candidate of rendered) {
      const id = candidate.outcome.id;
      if (!id || id === from.outcome.id) {
        continue;
      }
      const dx = candidate.cx - from.cx;
      const dy = candidate.cy - from.cy;
      if (direction[0] !== 0 && Math.sign(dx) !== direction[0]) {
        continue;
      }
      if (direction[1] !== 0 && Math.sign(dy) !== direction[1]) {
        continue;
      }
      const distance = Math.hypot(dx, dy);
      if (!nearest || distance < nearest.distance) {
        nearest = { id, distance };
      }
    }
    if (!nearest) {
      return;
    }
    setFocusedId(nearest.id);
    nodeRefs.current.get(nearest.id)?.focus();
  }

  function onNodeKeyDown(event: React.KeyboardEvent<HTMLButtonElement>, plot: PlottedOutcome) {
    const id = plot.outcome.id;
    if (!id) {
      return;
    }
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      onSelectOutcome(id);
      return;
    }
    if (event.key.startsWith("Arrow")) {
      event.preventDefault();
      focusInDirection(plot, event.key);
    }
  }

  return (
    <div
      className="opportunity-matrix"
      style={{ display: "grid", gridTemplateColumns: "1fr 320px", gap: 16 }}
    >
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

        <div
          className="opportunity-matrix__plot"
          style={{ position: "relative", width: "100%", aspectRatio: "500 / 360", minHeight: 320 }}
        >
          <svg
            role="img"
            aria-labelledby="opportunity-map-title"
            aria-describedby="opportunity-map-desc"
            viewBox="0 0 500 360"
            style={{ width: "100%", height: "100%", overflow: "visible" }}
          >
            <title id="opportunity-map-title">Opportunity map</title>
            <desc id="opportunity-map-desc">{summary}</desc>
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

            {/* Render Outcome Points. The SVG is one image with a summary; the
                real controls are the overlay buttons rendered below it. */}
            {rendered.map((plot) => {
              const { outcome, cx, cy } = plot;
              const isSelected = selectedOutcomeId === outcome.id;
              const isHovered = activeOutcome?.id === outcome.id;

              let nodeColor = plot.underserved ? "#fbbf24" : "var(--studio-indigo)";
              if (plot.score >= 15) nodeColor = "#f87171";

              return (
                <g key={outcome.id}>
                  {/* Pulse ring for underserved */}
                  {plot.underserved && (
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
                    filter={plot.underserved || isSelected ? "url(#glowEffect)" : undefined}
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

          {rendered.map((plot) => {
            const { outcome } = plot;
            const id = outcome.id;
            if (!id) {
              return null;
            }
            const isSelected = selectedOutcomeId === id;
            return (
              <button
                key={id}
                ref={(element) => {
                  if (element) {
                    nodeRefs.current.set(id, element);
                  } else {
                    nodeRefs.current.delete(id);
                  }
                }}
                type="button"
                className={`matrix-node${isSelected ? " matrix-node--selected" : ""}`}
                style={{ left: `${(plot.cx / 500) * 100}%`, top: `${(plot.cy / 360) * 100}%` }}
                tabIndex={id === rovingId ? 0 : -1}
                aria-pressed={isSelected}
                aria-label={`${id}, ${outcome.statement ?? "Outcome"}, opportunity score ${formatOpportunityScore(plot.score)}, ${plot.underserved ? "underserved" : "served"}`}
                onClick={() => onSelectOutcome(id)}
                onFocus={() => {
                  setFocusedId(id);
                  onHoverOutcome(outcome);
                }}
                onBlur={() => onHoverOutcome(null)}
                onMouseEnter={() => onHoverOutcome(outcome)}
                onMouseLeave={() => onHoverOutcome(null)}
                onKeyDown={(event) => onNodeKeyDown(event, plot)}
              />
            );
          })}

          <ul className="sr-only" aria-label="Opportunities on the map">
            {rendered.map((plot) => (
              <li key={plot.outcome.id}>
                {plot.outcome.id} — {plot.outcome.statement ?? "Outcome"}: importance{" "}
                {plot.importance}, satisfaction {plot.satisfaction}, opportunity score{" "}
                {formatOpportunityScore(plot.score)}
                {plot.underserved ? ", underserved" : ""}
              </li>
            ))}
          </ul>
          {capped ? (
            <p className="caption" role="status">
              Showing the {MATRIX_POINT_LIMIT} highest-opportunity outcomes of {plotted.length}.{" "}
              <button
                type="button"
                className="quiet-action"
                onClick={() => setShowAll(true)}
              >
                Plot all {plotted.length}
              </button>
            </p>
          ) : null}
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
                role="row"
                tabIndex={0}
                aria-selected={isSelected}
                onClick={() => outcome.id && onSelectOutcome(outcome.id)}
                onKeyDown={(event) => {
                  if ((event.key === "Enter" || event.key === " ") && outcome.id) {
                    event.preventDefault();
                    onSelectOutcome(outcome.id);
                  }
                }}
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
                  {formatOpportunityScore(outcome.opportunity_score)}
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
