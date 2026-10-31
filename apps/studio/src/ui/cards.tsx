import {
  formatOpportunityScore,
  isUnderserved,
  opportunityScore,
} from "../lib/odi";
import { readActions } from "./actions";
import { ActionRow, MeterBar, ScorePill, type NodeProps } from "./primitives";
import { num, str, type Tone } from "./props";
import { Markdown } from "../components/chat/Markdown";

/* ------------------------------------------------------------------ */
/* Shared readers                                                      */
/* ------------------------------------------------------------------ */

function record(value: unknown): Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function stringList(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function recordList(value: unknown): Record<string, unknown>[] {
  return Array.isArray(value) ? value.map(record) : [];
}

function scoreOf(source: Record<string, unknown>): number | null {
  const explicit = source.opportunityScore;
  if (typeof explicit === "number" && Number.isFinite(explicit)) {
    return explicit;
  }
  const importance = source.importance;
  const satisfaction = source.satisfaction;
  if (typeof importance === "number" && typeof satisfaction === "number") {
    return opportunityScore(importance, satisfaction);
  }
  return null;
}

function bandLabel(score: number | null): string {
  if (score == null) {
    return "Unscored";
  }
  return `${isUnderserved(score) ? "Underserved" : "Served"} · ${formatOpportunityScore(score)}`;
}

function bandTone(score: number | null): Tone {
  if (score == null) {
    return "neutral";
  }
  return isUnderserved(score) ? "warning" : "positive";
}

/* ------------------------------------------------------------------ */
/* outcome-card                                                        */
/* ------------------------------------------------------------------ */

export function OutcomeCard({ node }: NodeProps) {
  const id = str(node.props, "id", "Outcome");
  const statement = str(node.props, "statement");
  const importance = num(node.props, "importance", 0);
  const satisfaction = num(node.props, "satisfaction", 0);
  const evidence = str(node.props, "evidence");
  const score = scoreOf(node.props);
  const underserved = isUnderserved(score);
  const sample = node.props.sample === true;

  return (
    <article
      className={`ui-card ui-card--outcome${underserved ? " ui-card--urgent" : ""}`}
      aria-label={`Outcome ${id}`}
    >
      <header className="ui-card__head">
        <span className="ui-card__id">{id}</span>
        {sample ? (
          <span
            className="badge badge--amber"
            title="This is bundled sample data, not yours."
          >
            Sample
          </span>
        ) : null}
        <ScorePill tone={bandTone(score)}>{bandLabel(score)}</ScorePill>
      </header>

      <p className="ui-card__statement">{statement}</p>

      <div className="ui-card__meters">
        <MeterBar label="Importance" value={importance} tone="info" />
        <MeterBar label="Satisfaction today" value={satisfaction} tone={bandTone(score)} />
      </div>

      <p className="ui-card__formula">
        Opportunity = importance + max(importance − satisfaction, 0) ={" "}
        <b>{formatOpportunityScore(score)}</b>
      </p>

      {evidence ? (
        <blockquote className="ui-card__evidence">
          <Markdown source={evidence} />
        </blockquote>
      ) : null}

      <ActionRow actions={readActions(node.props)} />
    </article>
  );
}

/* ------------------------------------------------------------------ */
/* opportunity-thesis                                                  */
/* ------------------------------------------------------------------ */

export function OpportunityThesis({ node }: NodeProps) {
  const title = str(node.props, "title");
  const importance = num(node.props, "importance", 0);
  const satisfaction = num(node.props, "satisfaction", 0);
  const gap = str(node.props, "gap");
  const thesis = str(node.props, "thesis");
  const nextMove = str(node.props, "next_move") || str(node.props, "nextMove");
  const score = scoreOf(node.props);

  return (
    <article
      className={`ui-card ui-card--thesis${isUnderserved(score) ? " ui-card--urgent" : ""}`}
      aria-label={`Opportunity thesis: ${title}`}
    >
      <header className="ui-card__head">
        <span className="ui-card__id">Opportunity thesis</span>
        <ScorePill tone={bandTone(score)}>{bandLabel(score)}</ScorePill>
      </header>

      <h4 className="ui-card__title">{title}</h4>

      <div className="ui-card__meters">
        <MeterBar label="Importance" value={importance} tone="info" />
        <MeterBar label="Satisfaction today" value={satisfaction} tone={bandTone(score)} />
      </div>

      {gap ? (
        <p className="ui-thesis__gap">
          <b>The gap:</b> {gap}
        </p>
      ) : null}

      {thesis ? (
        <blockquote className="ui-thesis__claim">
          <Markdown source={thesis} />
        </blockquote>
      ) : null}

      {nextMove ? (
        <aside className="ui-callout ui-callout--info">
          <div className="ui-callout__body">
            <div className="ui-callout__title">Next move</div>
            <Markdown source={nextMove} />
          </div>
        </aside>
      ) : null}

      <ActionRow actions={readActions(node.props)} />
    </article>
  );
}

/* ------------------------------------------------------------------ */
/* opportunity-board                                                   */
/* ------------------------------------------------------------------ */

export function OpportunityBoard({ node }: NodeProps) {
  const title = str(node.props, "title");
  const rows = recordList(node.props.outcomes)
    .map((outcome) => ({
      id: str(outcome, "id", "—"),
      statement: str(outcome, "statement"),
      score: scoreOf(outcome),
    }))
    .sort((a, b) => (b.score ?? -Infinity) - (a.score ?? -Infinity));

  return (
    <article className="ui-card ui-card--board" aria-label={title || "Opportunity board"}>
      {title ? <h4 className="ui-card__title">{title}</h4> : null}

      <div className="ui-table-wrap">
        <table className="ui-table">
          <thead>
            <tr>
              <th scope="col">Outcome</th>
              <th scope="col">Opportunity</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => {
              const underserved = isUnderserved(row.score);
              return (
                <tr
                  className={underserved ? "ui-table__row--urgent" : undefined}
                  key={`${row.id}-${index}`}
                >
                  <td>
                    <span className="ui-card__id">{row.id}</span>
                    <span className="ui-table__statement">{row.statement}</span>
                  </td>
                  <td>
                    <ScorePill tone={bandTone(row.score)}>
                      {formatOpportunityScore(row.score)}
                    </ScorePill>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <ActionRow actions={readActions(node.props)} />
    </article>
  );
}

/* ------------------------------------------------------------------ */
/* impact-simulation                                                   */
/* ------------------------------------------------------------------ */

function Phase({ tone: phaseTone, label, items }: { tone: Tone; label: string; items: string[] }) {
  return (
    <div className={`ui-phase ui-tone--${phaseTone}`}>
      <div className="ui-phase__label">{label}</div>
      <ul className="ui-phase__items">
        {items.map((item, index) => (
          <li key={`${index}-${item.slice(0, 12)}`}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

export function ImpactSimulation({ node }: NodeProps) {
  const outcome = record(node.props.outcome);
  const outcomeId = str(outcome, "id", "Outcome");
  const statement = str(outcome, "statement");
  const bet = str(node.props, "bet");
  const verdict = str(node.props, "verdict");
  const metrics = recordList(node.props.metrics);
  const provenance = str(node.props, "provenance");

  return (
    <article
      className="ui-card ui-card--impact"
      aria-label={`Impact simulation for ${outcomeId}`}
    >
      <header className="ui-card__head">
        <span className="ui-card__id">{outcomeId}</span>
        <span className="ui-caption">Impact simulation</span>
        <span className="badge badge--amber">Simulated</span>
      </header>

      <p className="ui-card__statement">{statement}</p>

      {provenance === "simulated" ? (
        <p className="ui-caption">Simulated — no model behind this number</p>
      ) : null}

      <div className="ui-bet">
        <span className="ui-bet__label">The bet</span>
        <span className="ui-bet__value">{bet}</span>
      </div>

      <div className="ui-grid ui-grid--2 ui-gap--sm">
        <Phase tone="critical" label="Today" items={stringList(node.props.before)} />
        <Phase tone="positive" label="With this shipped" items={stringList(node.props.after)} />
      </div>

      {metrics.length > 0 ? (
        <div
          className={`ui-grid ui-grid--${Math.min(Math.max(metrics.length, 2), 3)} ui-gap--sm`}
        >
          {metrics.map((metric, index) => (
            <div className="ui-stat" key={`${index}-${str(metric, "label")}`}>
              <div className="ui-stat__label">{str(metric, "label")}</div>
              <div className="ui-stat__value">{str(metric, "value")}</div>
              {str(metric, "delta") ? (
                <div className="ui-stat__delta">{str(metric, "delta")}</div>
              ) : null}
            </div>
          ))}
        </div>
      ) : null}

      {verdict ? (
        <aside className="ui-callout ui-callout--info">
          <div className="ui-callout__body">
            <Markdown source={verdict} />
          </div>
        </aside>
      ) : null}

      <ActionRow actions={readActions(node.props)} />
    </article>
  );
}

/* ------------------------------------------------------------------ */
/* evidence-quote                                                      */
/* ------------------------------------------------------------------ */

const SEVERITY_TONE: Record<string, Tone> = {
  low: "neutral",
  medium: "info",
  high: "warning",
  critical: "critical",
};

export function EvidenceQuote({ node }: NodeProps) {
  const source = str(node.props, "source");
  const quote = str(node.props, "quote");
  const linkedTo = str(node.props, "linkedTo");
  const severity = str(node.props, "severity");

  return (
    <article className="ui-card ui-card--evidence" aria-label={`Evidence from ${source}`}>
      <header className="ui-card__head">
        <span className="ui-card__id">{source}</span>
        {severity ? (
          <ScorePill tone={SEVERITY_TONE[severity] ?? "neutral"}>{severity}</ScorePill>
        ) : null}
      </header>

      <blockquote className="ui-quote">
        <Markdown source={quote} />
      </blockquote>

      {linkedTo ? <p className="ui-caption">Linked to {linkedTo}</p> : null}

      <ActionRow actions={readActions(node.props)} />
    </article>
  );
}

/* ------------------------------------------------------------------ */
/* job-map                                                             */
/* ------------------------------------------------------------------ */

export function JobMap({ node }: NodeProps) {
  const job = str(node.props, "job");
  const steps = recordList(node.props.steps);

  return (
    <article className="ui-card ui-card--jobmap" aria-label={`Job map for ${job}`}>
      <header className="ui-card__head">
        <span className="ui-card__id">Job map</span>
      </header>
      <p className="ui-card__statement">{job}</p>

      <ol className="ui-jobmap">
        {steps.map((step, index) => {
          const stage = str(step, "stage");
          const note = str(step, "note");
          return (
            <li className="ui-jobmap__step" key={`${index}-${str(step, "name")}`}>
              <span className="ui-jobmap__index">{index + 1}</span>
              <span className="ui-jobmap__body">
                <span className="ui-jobmap__name">{str(step, "name")}</span>
                {stage ? <span className="ui-jobmap__stage">{stage}</span> : null}
                {note ? <span className="ui-jobmap__note">{note}</span> : null}
              </span>
            </li>
          );
        })}
      </ol>

      <ActionRow actions={readActions(node.props)} />
    </article>
  );
}

/* ------------------------------------------------------------------ */
/* decision-record                                                     */
/* ------------------------------------------------------------------ */

const STATUS_TONE: Record<string, Tone> = {
  proposed: "info",
  approved: "positive",
  rejected: "critical",
};

export function DecisionRecord({ node }: NodeProps) {
  const title = str(node.props, "title");
  const bet = str(node.props, "bet");
  const rationale = str(node.props, "rationale");
  const outcomeId = str(node.props, "outcomeId");
  const status = str(node.props, "status");

  return (
    <article className="ui-card ui-card--decision" aria-label={title}>
      <header className="ui-card__head">
        <span className="ui-card__id">Decision record</span>
        {status ? <ScorePill tone={STATUS_TONE[status] ?? "neutral"}>{status}</ScorePill> : null}
      </header>

      <h4 className="ui-card__title">{title}</h4>

      <dl className="ui-fields">
        <div className="ui-field">
          <dt>The bet</dt>
          <dd>{bet}</dd>
        </div>
        {outcomeId ? (
          <div className="ui-field">
            <dt>Serves</dt>
            <dd>{outcomeId}</dd>
          </div>
        ) : null}
        <div className="ui-field">
          <dt>Why</dt>
          <dd>
            <Markdown source={rationale} />
          </dd>
        </div>
      </dl>

      <ActionRow actions={readActions(node.props)} />
    </article>
  );
}

/* ------------------------------------------------------------------ */
/* outcome-compare                                                     */
/* ------------------------------------------------------------------ */

function compareCell(value: unknown): { text: string; measured: boolean } {
  const text = typeof value === "string" ? value : value == null ? "" : String(value);
  return { text, measured: text !== "not measured" };
}

export function OutcomeCompare({ node }: NodeProps) {
  const title = str(node.props, "title");
  const columns = stringList(node.props.columns);
  const rows = recordList(node.props.rows).map((row) => ({
    label: str(row, "label"),
    cells: (Array.isArray(row.cells) ? row.cells : []).map(compareCell),
  }));

  return (
    <article className="ui-card ui-card--compare" aria-label={title || "Comparison"}>
      {title ? <h4 className="ui-card__title">{title}</h4> : null}

      {rows.length > 0 && columns.length > 0 ? (
        <div className="ui-table-wrap">
          <table className="ui-table ui-table--compare">
            <thead>
              <tr>
                <th scope="col">Axis</th>
                {columns.map((column, index) => (
                  <th scope="col" key={`${column}-${index}`}>
                    {column}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, index) => (
                <tr key={`${row.label}-${index}`}>
                  <th scope="row">{row.label}</th>
                  {row.cells.map((cell, cellIndex) => (
                    <td key={cellIndex} className={cell.measured ? undefined : "ui-table__missing"}>
                      {cell.text || "—"}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="ui-brief__empty">Nothing to compare yet — pick two outcomes.</p>
      )}

      <ActionRow actions={readActions(node.props)} />
    </article>
  );
}

/* ------------------------------------------------------------------ */
/* opportunity-brief                                                   */
/* ------------------------------------------------------------------ */

const NOT_MEASURED = "not measured";

/** A band label for a score, or `not measured` when none was supplied. */
function briefBand(band: string, score: number | null): string {
  if (score == null) {
    return NOT_MEASURED;
  }
  const label = band || (isUnderserved(score) ? "underserved" : "overserved");
  return `${label} · ${formatOpportunityScore(score)}`;
}

function BriefOutcomeRow({ item }: { item: Record<string, unknown> }) {
  const statement = str(item, "statement");
  const band = str(item, "band");
  const score = typeof item.score === "number" && Number.isFinite(item.score) ? item.score : null;
  const n = typeof item.n === "number" && Number.isFinite(item.n) ? item.n : null;
  const method = str(item, "method");
  const quote = str(item, "quote");
  const source = str(item, "source");

  return (
    <li className="ui-brief__outcome">
      <p className="ui-brief__statement">{statement}</p>
      <div className="ui-brief__meta">
        <ScorePill tone={score == null ? "neutral" : isUnderserved(score) ? "warning" : "positive"}>
          {briefBand(band, score)}
        </ScorePill>
        <span className="ui-brief__sample">Sample: {n == null ? NOT_MEASURED : n}</span>
        {method ? <span className="ui-brief__method">Method: {method}</span> : null}
      </div>
      {quote ? <blockquote className="ui-brief__quote">“{quote}”</blockquote> : null}
      {source ? <p className="ui-brief__source">Source: {source}</p> : null}
    </li>
  );
}

export function OpportunityBrief({ node }: NodeProps) {
  const title = str(node.props, "title");
  const job = str(node.props, "job");
  const decision = str(node.props, "decision");
  const generatedAt = str(node.props, "generated_at");
  const evidenceCount =
    typeof node.props.evidence_count === "number" ? node.props.evidence_count : null;
  const outcomes = recordList(node.props.outcomes);

  return (
    <article className="ui-card ui-card--brief" aria-label={title || "Opportunity brief"}>
      <header className="ui-card__head">
        <span className="ui-card__id">The case</span>
        {evidenceCount != null ? (
          <span className="ui-brief__evidence">{evidenceCount} evidence records</span>
        ) : null}
      </header>

      <h4 className="ui-card__title">{title}</h4>
      <p className="ui-brief__job">{job}</p>

      {decision ? (
        <div className="ui-brief__decision">
          <span className="ui-brief__decision-label">The decision we are considering</span>
          <p>{decision}</p>
        </div>
      ) : null}

      {outcomes.length > 0 ? (
        <ul className="ui-brief__outcomes">
          {outcomes.map((item, index) => (
            <BriefOutcomeRow key={`${str(item, "statement")}-${index}`} item={item} />
          ))}
        </ul>
      ) : (
        <p className="ui-brief__empty">No scored outcomes yet — nothing to show here.</p>
      )}

      {generatedAt ? <p className="ui-brief__generated">Generated {generatedAt}</p> : null}

      <ActionRow actions={readActions(node.props)} />
    </article>
  );
}

/* ------------------------------------------------------------------ */
/* roadmap                                                             */
/* ------------------------------------------------------------------ */

function RoadmapMeasurement({ label, value }: { label: string; value: unknown }) {
  const measured = typeof value === "number" && Number.isFinite(value);
  return (
    <span className="ui-roadmap__measure">
      {label}: {measured ? formatOpportunityScore(value) : NOT_MEASURED}
    </span>
  );
}

export function Roadmap({ node }: NodeProps) {
  const title = str(node.props, "title");
  const entries = recordList(node.props.entries);
  const exclusionNote = str(node.props, "exclusion_note");
  const undecidedCount =
    typeof node.props.undecided_count === "number" ? node.props.undecided_count : null;

  const rows = entries.map((entry, index) => {
    const period = str(entry, "period");
    return {
      entry,
      index,
      period,
      showPeriod: period !== (index > 0 ? str(entries[index - 1], "period") : null),
    };
  });

  return (
    <article className="ui-card ui-card--roadmap" aria-label={title || "Outcome roadmap"}>
      {title ? <h4 className="ui-card__title">{title}</h4> : null}

      {entries.length > 0 ? (
        <ol className="ui-roadmap" aria-label="Roadmap entries">
          {rows.map(({ entry, index, period, showPeriod }) => {
            const statement = str(entry, "statement");
            const decisionId = str(entry, "decision_id");
            return (
              <li className="ui-roadmap__entry" key={`${decisionId}-${statement}-${index}`}>
                {showPeriod ? <span className="ui-roadmap__period">{period}</span> : null}
                <p className="ui-roadmap__statement">{statement}</p>
                <div className="ui-roadmap__meta">
                  <RoadmapMeasurement label="Baseline" value={entry.baseline} />
                  <RoadmapMeasurement label="Target" value={entry.target} />
                  <span className="ui-roadmap__decision">Decision: {decisionId}</span>
                </div>
              </li>
            );
          })}
        </ol>
      ) : (
        <p className="ui-brief__empty">No decisions yet.</p>
      )}

      {exclusionNote ? (
        <p className="ui-roadmap__exclusions">
          {undecidedCount != null ? `${undecidedCount} undecided · ` : ""}
          {exclusionNote}
        </p>
      ) : null}

      <ActionRow actions={readActions(node.props)} />
    </article>
  );
}

/* ------------------------------------------------------------------ */
/* decision-review                                                     */
/* ------------------------------------------------------------------ */

const REVIEW_TONE: Record<string, Tone> = {
  improved: "positive",
  degraded: "warning",
  "no change": "neutral",
  no_evidence: "neutral",
  orphaned: "critical",
};

/** A signed change with its sign, or `not measured` when a snapshot lacked it. */
function reviewChange(value: unknown): string {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return NOT_MEASURED;
  }
  const sign = value > 0 ? "+" : "";
  return `${sign}${formatOpportunityScore(value)}`;
}

function ReviewOutcomeRow({ item }: { item: Record<string, unknown> }) {
  const statement = str(item, "statement");
  const state = str(item, "state");
  return (
    <li className="ui-review__outcome">
      <div className="ui-review__head">
        <p className="ui-review__statement">{statement || str(item, "outcome_id")}</p>
        <ScorePill tone={REVIEW_TONE[state] ?? "neutral"}>{state || "no_evidence"}</ScorePill>
      </div>
      <div className="ui-review__meta">
        <span>Satisfaction: {reviewChange(item.satisfaction_change)}</span>
        <span>Importance: {reviewChange(item.importance_change)}</span>
        <span>Opportunity: {reviewChange(item.opportunity_change)}</span>
      </div>
    </li>
  );
}

export function DecisionReview({ node }: NodeProps) {
  const title = str(node.props, "title");
  const summary = str(node.props, "summary");
  const decidedAt = str(node.props, "decided_at");
  const daysElapsed =
    typeof node.props.days_elapsed === "number" ? node.props.days_elapsed : null;
  const outcomes = recordList(node.props.outcomes);

  return (
    <article className="ui-card ui-card--review" aria-label={title || "Decision review"}>
      <header className="ui-card__head">
        <span className="ui-card__id">Decision review</span>
        {daysElapsed != null ? (
          <span className="ui-review__elapsed">{daysElapsed} days ago</span>
        ) : null}
      </header>

      {title ? <h4 className="ui-card__title">{title}</h4> : null}
      {decidedAt ? <p className="ui-review__decided">Decided {decidedAt}</p> : null}
      {summary ? <p className="ui-review__summary">{summary}</p> : null}

      {outcomes.length > 0 ? (
        <ul className="ui-review__outcomes">
          {outcomes.map((item, index) => (
            <ReviewOutcomeRow key={`${str(item, "outcome_id")}-${index}`} item={item} />
          ))}
        </ul>
      ) : (
        <p className="ui-brief__empty">This decision chose no outcomes yet.</p>
      )}

      <ActionRow actions={readActions(node.props)} />
    </article>
  );
}

/* ------------------------------------------------------------------ */
/* bet                                                                 */
/* ------------------------------------------------------------------ */

const BET_TONE: Record<string, Tone> = {
  planned: "neutral",
  running: "info",
  measured: "positive",
  abandoned: "critical",
};

/** A measurement with no sign, or `not measured` when none was supplied. */
function measurement(value: unknown): string {
  return typeof value === "number" && Number.isFinite(value)
    ? formatOpportunityScore(value)
    : NOT_MEASURED;
}

export function Bet({ node }: NodeProps) {
  const title = str(node.props, "title");
  const hypothesis = str(node.props, "hypothesis");
  const outcomeId = str(node.props, "outcome_id");
  const measureBy = str(node.props, "measure_by");
  const status = str(node.props, "status");

  return (
    <article className="ui-card ui-card--bet" aria-label={title || "Bet"}>
      <header className="ui-card__head">
        <span className="ui-card__id">Bet</span>
        {status ? <ScorePill tone={BET_TONE[status] ?? "neutral"}>{status}</ScorePill> : null}
      </header>

      {title ? <h4 className="ui-card__title">{title}</h4> : null}
      <p className="ui-bet__hypothesis">{hypothesis}</p>

      <dl className="ui-fields">
        <div className="ui-field">
          <dt>Baseline</dt>
          <dd>{measurement(node.props.baseline)}</dd>
        </div>
        <div className="ui-field">
          <dt>Target</dt>
          <dd>{measurement(node.props.target)}</dd>
        </div>
        <div className="ui-field">
          <dt>Measure by</dt>
          <dd>{measureBy || NOT_MEASURED}</dd>
        </div>
        {outcomeId ? (
          <div className="ui-field">
            <dt>Serves</dt>
            <dd>{outcomeId}</dd>
          </div>
        ) : null}
      </dl>

      <ActionRow actions={readActions(node.props)} />
    </article>
  );
}

const BAND_TONE: Record<string, Tone> = {
  underserved: "warning",
  appropriate: "positive",
  overserved: "critical",
  unscored: "neutral",
};

export function SegmentProfile({ node }: NodeProps) {
  const title = str(node.props, "title");
  const strategy = str(node.props, "strategy");
  const gaps = stringList(node.props.gaps);
  const total = num(node.props, "total_members", 0);
  const measured = num(node.props, "measured_count", 0);
  const ratio = typeof node.props.measured_ratio === "number" ? node.props.measured_ratio : null;

  return (
    <article className="ui-card ui-card--segment-profile" aria-label={title || "Segment profile"}>
      <header className="ui-card__head">
        <span className="ui-card__id">Segment</span>
        {title ? <h4 className="ui-card__title">{title}</h4> : null}
      </header>

      <dl className="ui-fields">
        <div className="ui-field">
          <dt>Members</dt>
          <dd>{total}</dd>
        </div>
        <div className="ui-field">
          <dt>Measured</dt>
          <dd>
            {measured}
            {ratio == null ? ` · ${NOT_MEASURED}` : ` · ${Math.round(ratio * 100)}%`}
          </dd>
        </div>
        <div className="ui-field">
          <dt>Underserved</dt>
          <dd>{num(node.props, "underserved_count", 0)}</dd>
        </div>
        <div className="ui-field">
          <dt>Overserved</dt>
          <dd>{num(node.props, "overserved_count", 0)}</dd>
        </div>
      </dl>

      {(["top_underserved", "top_overserved"] as const).map((key) => {
        const entries = recordList(node.props[key]);
        if (entries.length === 0) {
          return null;
        }
        return (
          <div className="ui-segment__group" key={key}>
            <h5 className="ui-segment__legend">
              {key === "top_underserved" ? "Most underserved" : "Most overserved"}
            </h5>
            <ul className="ui-segment__list">
              {entries.map((entry, index) => (
                <li key={`${key}-${index}`}>
                  <span>{str(entry, "statement") || str(entry, "outcome_id")}</span>
                  <ScorePill tone={BAND_TONE[str(entry, "band")] ?? "neutral"}>
                    {measurement(entry.score)}
                  </ScorePill>
                </li>
              ))}
            </ul>
          </div>
        );
      })}

      {strategy ? <p className="ui-segment__strategy">{strategy}</p> : null}

      {gaps.length > 0 ? (
        <ul className="ui-segment__gaps">
          {gaps.map((gap, index) => (
            <li key={`gap-${index}`}>{gap}</li>
          ))}
        </ul>
      ) : null}

      <ActionRow actions={readActions(node.props)} />
    </article>
  );
}
