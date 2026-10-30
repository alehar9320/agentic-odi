import { useState } from "react";

import { useStudio } from "../../state/StudioContext";
import type { Signal, SignalKind, SignalSeverity } from "../../types";
import { FailurePanel } from "../FailurePanel";
import {
  BoltIcon,
  CheckIcon,
  CompassIcon,
  RouteIcon,
  SignalIcon,
  SparkIcon,
} from "../icons";

type FilterType = "all" | "unread" | "urgent" | "outcome" | "evidence" | "agent";

const KIND_LABEL: Record<SignalKind, string> = {
  job_added: "Job",
  outcome_scored: "Outcome",
  opportunity_crossed: "Opportunity",
  evidence_ingested: "Evidence",
  evidence_promoted: "Evidence",
  job_map_completed: "Job map",
  agent_work_completed: "Agent work",
  agent_work_failed: "Agent work",
  agent_work_blocked: "Agent work",
};

const SEVERITY_BADGE: Record<SignalSeverity, string> = {
  info: "badge--blue",
  notice: "badge--green",
  urgent: "badge--amber",
};

function formatRelativeTime(isoString: string): string {
  try {
    const date = new Date(isoString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / (1000 * 60));
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffMins < 1) return "Just now";
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    return `${diffDays}d ago`;
  } catch {
    return "Recently";
  }
}

function kindIcon(kind: SignalKind) {
  if (kind === "job_added" || kind === "job_map_completed") return <RouteIcon size={16} />;
  if (kind === "outcome_scored" || kind === "opportunity_crossed") return <CompassIcon size={16} />;
  if (kind === "evidence_promoted") return <SparkIcon size={16} />;
  if (kind.startsWith("agent_work_")) return <BoltIcon size={16} />;
  return <SignalIcon size={16} />;
}

function isAgentWorkSignal(signal: Signal): boolean {
  return signal.kind.startsWith("agent_work_");
}

function isOutcomeSignal(signal: Signal): boolean {
  return signal.kind === "outcome_scored" || signal.kind === "opportunity_crossed";
}

function isEvidenceSignal(signal: Signal): boolean {
  return signal.kind === "evidence_ingested" || signal.kind === "evidence_promoted";
}

/**
 * The inbox the store actually holds. Simulated events (#78) stay visible so a
 * developer can see what a full feed looks like, but they are labelled and are
 * counted nowhere — the numbers on this page describe recorded activity only.
 */
export function CatchUpFeed() {
  const {
    signals,
    signalsError,
    unreadSignalCount,
    refreshSignals,
    markSignalAsRead,
    dismissSignal,
    focusSignalSubject,
    simulateBackgroundEvent,
  } = useStudio();

  const [activeFilter, setActiveFilter] = useState<FilterType>("all");

  const recorded = signals.filter((signal) => !signal.simulated);
  const unread = recorded.filter((signal) => !signal.read_at);
  const urgentCount = unread.filter((signal) => signal.severity === "urgent").length;
  const outcomeCount = recorded.filter(isOutcomeSignal).length;
  const evidenceCount = recorded.filter(isEvidenceSignal).length;
  const agentCount = recorded.filter(isAgentWorkSignal).length;

  const visible = signals.filter((signal) => {
    if (activeFilter === "unread") return !signal.simulated && !signal.read_at;
    if (activeFilter === "urgent") return !signal.simulated && signal.severity === "urgent";
    if (activeFilter === "outcome") return isOutcomeSignal(signal) && !signal.simulated;
    if (activeFilter === "evidence") return isEvidenceSignal(signal) && !signal.simulated;
    if (activeFilter === "agent") return isAgentWorkSignal(signal) && !signal.simulated;
    return true;
  });

  function activate(signal: Signal) {
    focusSignalSubject(signal);
  }

  function handleCardKey(event: React.KeyboardEvent, signal: Signal) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      activate(signal);
    }
  }

  const chips: Array<{ id: FilterType; label: string; count: number }> = [
    { id: "all", label: "All", count: recorded.length },
    { id: "unread", label: "Unread", count: unreadSignalCount },
    { id: "urgent", label: "Urgent", count: urgentCount },
    { id: "outcome", label: "Outcome shifts", count: outcomeCount },
    { id: "evidence", label: "Evidence", count: evidenceCount },
    { id: "agent", label: "Agent work", count: agentCount },
  ];

  return (
    <div className="stack catchup-feed" aria-label="Signal inbox">
      <section className="catchup-summary card" aria-label="Summary while you were away">
        <div className="card__head">
          <div>
            <span className="hero__eyebrow">Signals from the store</span>
            <h2 className="catchup-title">While you were away</h2>
          </div>
          <div className="catchup-summary__actions">
            <button
              type="button"
              className="button button--ghost"
              onClick={() => void refreshSignals()}
              title="Re-read the inbox from the store"
            >
              Refresh
            </button>
            <button
              type="button"
              className="button button--ghost"
              onClick={simulateBackgroundEvent}
              title="Add a labelled demonstration signal. It is not recorded in the store."
            >
              + Simulate update
            </button>
          </div>
        </div>

        <div className="metrics catchup-metrics">
          <div className="metric">
            <span className="metric__label">Unread signals</span>
            <span className="metric__value metric__value--accent">{unreadSignalCount}</span>
          </div>
          <div className="metric">
            <span className="metric__label">Urgent</span>
            <span className="metric__value">{urgentCount}</span>
          </div>
          <div className="metric">
            <span className="metric__label">Outcome shifts</span>
            <span className="metric__value">{outcomeCount}</span>
          </div>
        </div>
      </section>

      {signalsError ? (
        <FailurePanel error={signalsError} onRetry={() => void refreshSignals()} />
      ) : null}

      <div className="chips" role="group" aria-label="Filter signals">
        {chips.map((chip) => (
          <button
            key={chip.id}
            type="button"
            className={`chip${activeFilter === chip.id ? " is-on" : ""}`}
            aria-pressed={activeFilter === chip.id}
            onClick={() => setActiveFilter(chip.id)}
          >
            {chip.label} ({chip.count})
          </button>
        ))}
      </div>

      {visible.length === 0 ? (
        <div className="card empty-note catchup-empty">
          <span className="catchup-empty__icon" aria-hidden="true">
            <BoltIcon size={18} />
          </span>
          <p className="catchup-empty__title">
            {recorded.length === 0 ? "Nothing happened while you were away." : "No signals match."}
          </p>
          <p className="catchup-empty__hint">
            {recorded.length === 0
              ? "This inbox only fills from real changes: an outcome re-scored, evidence captured, a job map completed, or an agent finishing work."
              : "Try another filter."}
          </p>
        </div>
      ) : (
        <div className="cards">
          {visible.map((item) => {
            const unreadCard = !item.simulated && !item.read_at;
            return (
              <article
                key={item.id}
                role="button"
                tabIndex={0}
                aria-label={`${item.title}. Activate to ${
                  item.subject_id ? `open the ${item.subject_kind ?? "record"} it names` : "mark as read"
                }`}
                className={`card catchup-card${unreadCard ? " is-unread" : ""}${
                  item.simulated ? " is-simulated" : ""
                }`}
                onClick={() => activate(item)}
                onKeyDown={(event) => handleCardKey(event, item)}
              >
                <div className="card__head">
                  <div className="catchup-card__meta">
                    {unreadCard && <span className="status-dot" title="Unread signal" />}
                    <span className={`badge ${SEVERITY_BADGE[item.severity]}`}>
                      <span className="catchup-card__badge">
                        {kindIcon(item.kind)}
                        {KIND_LABEL[item.kind].toUpperCase()} · {item.severity}
                      </span>
                    </span>
                    {item.simulated ? (
                      <span
                        className="badge badge--amber"
                        title="Demonstration event, not recorded in the store"
                      >
                        Simulated
                      </span>
                    ) : null}
                    <span className="card__id">{formatRelativeTime(item.created_at)}</span>
                  </div>

                  <div className="catchup-card__controls">
                    {!item.read_at && !item.simulated ? (
                      <button
                        type="button"
                        className="quiet-action"
                        title="Mark as read"
                        onClick={(event) => {
                          event.stopPropagation();
                          markSignalAsRead(item.id);
                        }}
                      >
                        <CheckIcon size={14} />
                        Read
                      </button>
                    ) : null}
                    <button
                      type="button"
                      className="quiet-action quiet-action--danger"
                      title="Dismiss this signal"
                      onClick={(event) => {
                        event.stopPropagation();
                        dismissSignal(item.id);
                      }}
                    >
                      Dismiss
                    </button>
                  </div>
                </div>

                <h3 className="catchup-card__title">{item.title}</h3>
                {item.detail ? <p className="card__statement catchup-card__body">{item.detail}</p> : null}

                <div className="card__actions">
                  {item.subject_id ? (
                    <button
                      type="button"
                      className="button button--ghost catchup-card__action"
                      onClick={(event) => {
                        event.stopPropagation();
                        activate(item);
                      }}
                    >
                      {item.subject_kind === "outcome" || item.subject_kind === "step"
                        ? "View outcome"
                        : item.subject_kind === "evidence"
                          ? "Open the evidence"
                          : item.subject_kind === "agent_work"
                            ? "Open the work item"
                            : `Open the ${item.subject_kind ?? "record"}`} →
                    </button>
                  ) : (
                    <button
                      type="button"
                      className="button button--ghost catchup-card__action"
                      onClick={(event) => {
                        event.stopPropagation();
                        markSignalAsRead(item.id);
                      }}
                    >
                      Mark as read
                    </button>
                  )}
                </div>
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
}
