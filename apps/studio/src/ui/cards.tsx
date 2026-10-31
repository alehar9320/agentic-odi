import { useState } from "react";

import {
  formatOpportunityScore,
  isUnderserved,
  opportunityScore,
} from "../lib/odi";
import { useStudio } from "../state/StudioContext";
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
/* candidate-queue                                                     */
/* ------------------------------------------------------------------ */

const QUEUE_STATE_TONE: Record<string, Tone> = {
  loading: "info",
  ready: "neutral",
  empty: "neutral",
  failed: "critical",
};

const DECISION_TONE: Record<string, Tone> = {
  proposed: "info",
  accepted: "positive",
  merged: "positive",
  rejected: "critical",
};

/**
 * The review queue: each proposed candidate beside the sentence it came from.
 *
 * The card is a view, never an actor. Every decision is an intent the agent
 * turns into the same `PATCH /api/candidates/{id}` call the CLI uses, so there
 * is one state machine and one audit trail. A candidate is only ever shown as
 * decided because the agent said the write succeeded — this component never
 * removes a row on a click.
 */
export function CandidateQueue({ node }: NodeProps) {
  const interviewId = str(node.props, "interviewId");
  const state = str(node.props, "state", "ready");
  const message = str(node.props, "message");
  const target = str(node.props, "target");
  const candidates = recordList(node.props.candidates);
  const actions = readActions(node.props);

  const header = (
    <header className="ui-card__head">
      <span className="ui-card__id">Review queue</span>
      <ScorePill tone={QUEUE_STATE_TONE[state] ?? "neutral"}>{state}</ScorePill>
    </header>
  );

  if (state === "loading") {
    return (
      <article
        className="ui-card ui-card--queue"
        aria-busy="true"
        aria-label="Loading the review queue"
      >
        {header}
        <p className="ui-caption">Loading the proposed candidates…</p>
        <ActionRow actions={actions} />
      </article>
    );
  }

  if (state === "failed") {
    return (
      <article
        className="ui-card ui-card--queue ui-card--urgent"
        aria-label="The review queue could not be loaded"
      >
        {header}
        <p className="ui-card__statement">{message || "The review queue could not be loaded."}</p>
        <ActionRow actions={actions} />
      </article>
    );
  }

  if (state === "empty" || candidates.length === 0) {
    return (
      <article className="ui-card ui-card--queue" aria-label="Nothing to review">
        {header}
        <p className="ui-caption">{message || "Nothing is waiting for review."}</p>
        <ActionRow actions={actions} />
      </article>
    );
  }

  return (
    <article className="ui-card ui-card--queue" aria-label="Review queue">
      {header}
      <p className="ui-caption">
        {target
          ? `Merging folds a candidate's sentence into outcome ${target}.`
          : "A merge needs an accepted outcome to fold into; accept one first."}
      </p>

      <ol className="ui-queue">
        {candidates.map((candidate, index) => {
          const id = str(candidate, "id", "candidate");
          const statement = str(candidate, "statement");
          const quote = str(candidate, "quote");
          const source = str(candidate, "source");
          const decision = str(candidate, "decision");
          const note = str(candidate, "note");
          const confidence = candidate.confidence;
          return (
            <li className="ui-queue__item" key={`${id}-${index}`}>
              <div className="ui-queue__head">
                <span className="ui-card__id">{id}</span>
                {decision ? (
                  <ScorePill tone={DECISION_TONE[decision] ?? "neutral"}>{decision}</ScorePill>
                ) : typeof confidence === "number" ? (
                  <span className="ui-caption">{Math.round(confidence * 100)}% confidence</span>
                ) : null}
              </div>
              <p className="ui-card__statement">{statement}</p>
              <blockquote className="ui-quote">
                <Markdown source={quote} />
              </blockquote>
              {source ? <p className="ui-caption">From {source}</p> : null}
              {note ? <p className="ui-queue__note">{note}</p> : null}
            </li>
          );
        })}
      </ol>

      {interviewId ? <p className="ui-caption">Interview {interviewId}</p> : null}

      <ActionRow actions={actions} />
    </article>
  );
}

/* batch-scoring                                                       */
/* ------------------------------------------------------------------ */

interface AppliedScore {
  index: number;
  id: string;
  /** The pair the outcome held before this write; `null` is truly unscored. */
  importance: number | null;
  satisfaction: number | null;
}

/**
 * The same pass as `odi score`, driven from the thread.
 *
 * One outcome at a time, with the customer's sentence in view. Every write goes
 * through the shared `score-batch` endpoint — one item per call — so a click
 * and a keypress reach the same store and the same 1–10 bounds. Progress moves
 * only after the server reports a result: a refused write leaves the person on
 * the same outcome with the reason beside it, never silently on the next one.
 */
export function BatchScoring({ node }: NodeProps) {
  const { scoreOutcome } = useStudio();
  const state = str(node.props, "state", "ready");
  const outcomes = recordList(node.props.outcomes);
  const message = str(node.props, "message");

  const [index, setIndex] = useState(0);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const [applied, setApplied] = useState<AppliedScore[]>([]);
  const [tally, setTally] = useState({ scored: 0, skipped: 0, undone: 0 });

  const current = outcomes[index];
  const total = outcomes.length;
  const actions = readActions(node.props);

  if (state === "loading") {
    return (
      <article
        className="ui-card ui-card--scoring"
        aria-label="Loading the scoring pass"
        aria-busy="true"
      >
        <p className="ui-caption">Assembling the pass…</p>
      </article>
    );
  }

  if (state === "failed") {
    return (
      <article className="ui-card ui-card--scoring" aria-label="The scoring pass could not be loaded">
        <header className="ui-card__head">
          <span className="ui-card__id">Scoring pass</span>
        </header>
        <p className="ui-card__statement">{message || "The pass could not be loaded."}</p>
        <ActionRow actions={actions} />
      </article>
    );
  }

  if (state === "empty" || total === 0) {
    return (
      <article className="ui-card ui-card--scoring" aria-label="Nothing to score">
        <header className="ui-card__head">
          <span className="ui-card__id">Scoring pass</span>
        </header>
        <p className="ui-card__statement">{message || "Nothing to score: no outcomes match."}</p>
        <ActionRow actions={actions} />
      </article>
    );
  }

  if (index >= total) {
    const parts = [`scored ${tally.scored}`, `skipped ${tally.skipped}`];
    if (tally.undone) {
      parts.push(`undone ${tally.undone}`);
    }
    return (
      <article className="ui-card ui-card--scoring" aria-label="Scoring pass complete">
        <header className="ui-card__head">
          <span className="ui-card__id">Scoring pass</span>
          <span className="ui-caption">Complete</span>
        </header>
        <p className="ui-card__statement">Scoring complete: {parts.join(", ")}.</p>
        <ActionRow actions={actions} />
      </article>
    );
  }

  function recordWrite(importance: number | null, satisfaction: number | null) {
    setApplied((prev) => [...prev, { index, id: str(current, "id"), importance, satisfaction }]);
    setTally((prev) => ({ ...prev, scored: prev.scored + 1 }));
    setIndex((prev) => prev + 1);
  }

  function score(importance: number, satisfaction: number) {
    if (busy) {
      return;
    }
    setBusy(true);
    setNote(null);
    void scoreOutcome({ outcome_id: str(current, "id"), importance, satisfaction })
      .then((result) => {
        if (!result.ok) {
          setNote(result.error ?? "The server refused this score.");
          return;
        }
        recordWrite(
          typeof current.importance === "number" ? current.importance : null,
          typeof current.satisfaction === "number" ? current.satisfaction : null,
        );
      })
      .catch((error: unknown) => {
        setNote((error as Error).message);
      })
      .finally(() => setBusy(false));
  }

  function skip() {
    if (busy) {
      return;
    }
    setTally((prev) => ({ ...prev, skipped: prev.skipped + 1 }));
    setIndex((prev) => prev + 1);
  }

  function undo() {
    if (busy || applied.length === 0) {
      return;
    }
    const last = applied[applied.length - 1];
    setBusy(true);
    setNote(null);
    // Undo replays the previous pair through the same endpoint; a prior
    // null/null restores the outcome to truly unscored rather than to zero.
    void scoreOutcome({
      outcome_id: last.id,
      importance: last.importance,
      satisfaction: last.satisfaction,
    })
      .then((result) => {
        if (!result.ok) {
          setNote(result.error ?? "The server refused to undo this score.");
          return;
        }
        setApplied((prev) => prev.slice(0, -1));
        setTally((prev) => ({
          scored: Math.max(prev.scored - 1, 0),
          skipped: prev.skipped,
          undone: prev.undone + 1,
        }));
        setIndex(last.index);
      })
      .catch((error: unknown) => {
        setNote((error as Error).message);
      })
      .finally(() => setBusy(false));
  }

  return (
    <ScoringStep
      key={`${index}:${str(current, "id")}`}
      outcome={current}
      position={index + 1}
      total={total}
      busy={busy}
      note={note}
      canUndo={applied.length > 0}
      onScore={score}
      onSkip={skip}
      onUndo={undo}
      actions={actions}
    />
  );
}

interface ScoringStepProps {
  outcome: Record<string, unknown>;
  position: number;
  total: number;
  busy: boolean;
  note: string | null;
  canUndo: boolean;
  onScore: (importance: number, satisfaction: number) => void;
  onSkip: () => void;
  onUndo: () => void;
  actions: ReturnType<typeof readActions>;
}

/**
 * One outcome on stage. Keyed by id, so its controls start from this outcome's
 * own scores; an unscored outcome opens at the middle rather than pretending a
 * prior pair exists.
 */
function ScoringStep({
  outcome,
  position,
  total,
  busy,
  note,
  canUndo,
  onScore,
  onSkip,
  onUndo,
  actions,
}: ScoringStepProps) {
  const outcomeId = str(outcome, "id");
  const statement = str(outcome, "statement");
  const quote = str(outcome, "quote");
  const wasScored =
    typeof outcome.importance === "number" && typeof outcome.satisfaction === "number";
  const [importance, setImportance] = useState(() =>
    typeof outcome.importance === "number" ? outcome.importance : 5,
  );
  const [satisfaction, setSatisfaction] = useState(() =>
    typeof outcome.satisfaction === "number" ? outcome.satisfaction : 5,
  );

  return (
    <article className="ui-card ui-card--scoring" aria-label={`Scoring pass ${position} of ${total}`}>
      <header className="ui-card__head">
        <span className="ui-card__id">{outcomeId}</span>
        <span className="ui-caption">
          {position}/{total}
        </span>
      </header>

      <p className="ui-card__statement">{statement}</p>

      <p className="ui-caption">
        {wasScored
          ? `Current · importance ${outcome.importance} · satisfaction ${outcome.satisfaction}`
          : "Current · unscored"}
      </p>

      {quote ? (
        <blockquote className="ui-quote">
          <Markdown source={quote} />
        </blockquote>
      ) : (
        <p className="ui-caption">No customer sentence was captured for this outcome.</p>
      )}

      <label className="ui-scoring__field" htmlFor={`score-importance-${outcomeId}`}>
        Importance · {importance.toFixed(1)}
        <input
          id={`score-importance-${outcomeId}`}
          type="range"
          min={1}
          max={10}
          step={0.1}
          value={importance}
          disabled={busy}
          onChange={(event) => setImportance(Number(event.target.value))}
        />
      </label>

      <label className="ui-scoring__field" htmlFor={`score-satisfaction-${outcomeId}`}>
        Satisfaction · {satisfaction.toFixed(1)}
        <input
          id={`score-satisfaction-${outcomeId}`}
          type="range"
          min={1}
          max={10}
          step={0.1}
          value={satisfaction}
          disabled={busy}
          onChange={(event) => setSatisfaction(Number(event.target.value))}
        />
      </label>

      <p className="ui-caption">
        Opportunity <b>{formatOpportunityScore(opportunityScore(importance, satisfaction))}</b>
      </p>

      {note ? (
        <aside className="ui-callout ui-callout--warning" role="alert">
          <div className="ui-callout__body">{note}</div>
        </aside>
      ) : null}

      <div className="ui-actions">
        <button
          type="button"
          className="ui-action ui-action--primary"
          disabled={busy}
          onClick={() => onScore(importance, satisfaction)}
        >
          {busy ? "Saving…" : "Score"}
        </button>
        <button type="button" className="ui-action ui-action--ghost" disabled={busy} onClick={onSkip}>
          Skip
        </button>
        <button
          type="button"
          className="ui-action ui-action--ghost"
          disabled={busy || !canUndo}
          onClick={onUndo}
        >
          Undo
        </button>
      </div>

      <ActionRow actions={actions} />
    </article>
  );
}
