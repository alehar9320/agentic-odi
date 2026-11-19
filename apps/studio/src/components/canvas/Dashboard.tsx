import { useEffect, useMemo, useState } from "react";

import { asStudioError, fetchStudies } from "../../api/studioApi";
import {
  bucketSignalsByDay,
  countSignalsInRange,
  formatRangeLabel,
  resolveRange,
  type DashboardRange,
} from "../../lib/dashboard";
import { formatMemberMean, scoredAverage } from "../../lib/odi";
import { useStudio } from "../../state/StudioContext";
import type { Signal, StudioError, Study } from "../../types";
import { FailurePanel } from "../FailurePanel";

const RANGES: Array<{ id: DashboardRange; label: string }> = [
  { id: "today", label: "Today" },
  { id: "week", label: "This week" },
  { id: "all", label: "All time" },
];

/**
 * The trend, drawn by hand.
 *
 * No charting dependency: a small inline SVG in the same hand-drawn style as
 * the opportunity landscape. An empty series is an empty axis, never a flat
 * line standing in for data that does not exist.
 */
function TrendChart({ buckets }: { buckets: Array<{ label: string; count: number }> }) {
  if (buckets.length === 0) {
    return (
      <p className="empty-note">No signals recorded in this range yet — the axis is empty.</p>
    );
  }

  const width = 320;
  const height = 72;
  const max = Math.max(1, ...buckets.map((bucket) => bucket.count));
  const step = buckets.length > 1 ? width / (buckets.length - 1) : 0;
  const points = buckets.map((bucket, index) => {
    const x = buckets.length > 1 ? index * step : width / 2;
    const y = height - (bucket.count / max) * (height - 8) - 4;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });

  return (
    <svg
      className="dashboard-trend__svg"
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label={`Signal volume over ${buckets.length} day(s)`}
      preserveAspectRatio="none"
    >
      <polyline
        points={points.join(" ")}
        fill="none"
        stroke="var(--accent)"
        strokeWidth="1.6"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  );
}

/**
 * The dashboard lens: where a PM's attention should go, before any thread is
 * opened. Every number is read from a record the store already holds; a metric
 * with no records reads as `0` or "Not scored", never as an invented value.
 */
export function Dashboard() {
  const { signals, unreadSignalCount, canvas, strategy, settings } = useStudio();
  const [range, setRange] = useState<DashboardRange>("week");
  const [studies, setStudies] = useState<Study[]>([]);
  const [studiesError, setStudiesError] = useState<StudioError | null>(null);

  const { from, to } = useMemo(() => resolveRange(range), [range]);

  useEffect(() => {
    let cancelled = false;
    fetchStudies(settings.mcp_url)
      .then((result) => {
        if (!cancelled) {
          setStudies(result);
          setStudiesError(null);
        }
      })
      .catch((error: unknown) => {
        // A failed read keeps the last values on screen; it never empties them.
        if (!cancelled) {
          setStudiesError(asStudioError(error));
        }
      });
    return () => {
      cancelled = true;
    };
  }, [settings.mcp_url]);

  const outcomesScored = useMemo(
    () => countSignalsInRange(signals as Signal[], "outcome_scored", from, to),
    [signals, from, to],
  );
  const gapSummary = useMemo(() => scoredAverage(canvas?.outcomes ?? []), [canvas]);
  const studiesOpened = useMemo(
    () =>
      studies.filter((study) => {
        const time = new Date(study.opened_at).getTime();
        if (Number.isNaN(time)) {
          return false;
        }
        if (from && time < from.getTime()) {
          return false;
        }
        if (to && time >= to.getTime()) {
          return false;
        }
        return true;
      }).length,
    [studies, from, to],
  );
  const buckets = useMemo(() => bucketSignalsByDay(signals as Signal[], from, to), [signals, from, to]);

  const cards: Array<{ label: string; value: string }> = [
    { label: "Outcomes scored", value: String(outcomesScored) },
    { label: "Average opportunity gap", value: formatMemberMean(gapSummary) },
    { label: "Signals pending review", value: String(unreadSignalCount) },
    { label: "Studies opened", value: String(studiesOpened) },
    { label: "Active strategy bets", value: String(strategy?.bets.length ?? 0) },
  ];

  return (
    <div className="stack dashboard" role="region" aria-label="Dashboard">
      <div className="chips" role="group" aria-label="Date range">
        {RANGES.map((option) => (
          <button
            key={option.id}
            type="button"
            className={`chip${range === option.id ? " is-on" : ""}`}
            aria-pressed={range === option.id}
            onClick={() => setRange(option.id)}
          >
            {option.label}
          </button>
        ))}
      </div>

      <div className="metrics" aria-label="Headline metrics">
        {cards.map((card) => (
          <div key={card.label} className="metric">
            <span className="metric__label">{card.label}</span>
            <span className="metric__value">{card.value}</span>
          </div>
        ))}
      </div>

      {studiesError ? <FailurePanel error={studiesError} /> : null}

      <section className="card dashboard-trend" aria-label="Signal volume">
        <div className="card__head">
          <span className="card__id">Signal volume · {formatRangeLabel(range)}</span>
          <span className="card__meta">{buckets.reduce((sum, b) => sum + b.count, 0)} signals</span>
        </div>
        <TrendChart buckets={buckets} />
      </section>
    </div>
  );
}
