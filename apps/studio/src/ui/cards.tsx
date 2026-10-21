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

  return (
    <article
      className={`ui-card ui-card--outcome${underserved ? " ui-card--urgent" : ""}`}
      aria-label={`Outcome ${id}`}
    >
      <header className="ui-card__head">
        <span className="ui-card__id">{id}</span>
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

  return (
    <article
      className="ui-card ui-card--impact"
      aria-label={`Impact simulation for ${outcomeId}`}
    >
      <header className="ui-card__head">
        <span className="ui-card__id">{outcomeId}</span>
        <span className="ui-caption">Impact simulation</span>
      </header>

      <p className="ui-card__statement">{statement}</p>

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
