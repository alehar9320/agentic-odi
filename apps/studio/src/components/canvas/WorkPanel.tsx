import { useCallback, useEffect, useState } from "react";

import {
  cancelWorkItem,
  getOrchestratorStatus,
  listWorkItems,
  retryWorkItem,
} from "../../api/studioApi";
import { useStudio } from "../../state/StudioContext";
import type { AgentWorkEntry, OrchestratorStatus, WorkItemStatus } from "../../types";

const STATUS_TONE: Record<WorkItemStatus, string> = {
  queued: "badge",
  dispatching: "badge badge--blue",
  running: "badge badge--blue",
  waiting_for_confirmation: "badge badge--blue",
  completed: "badge badge--green",
  failed: "badge badge--amber",
  blocked: "badge badge--amber",
  cancelled: "badge",
};

const ACTIVE: WorkItemStatus[] = [
  "queued",
  "dispatching",
  "running",
  "waiting_for_confirmation",
];

function statusLabel(status: WorkItemStatus): string {
  return status === "waiting_for_confirmation" ? "waiting on confirmation" : status;
}

function costLabel(run: AgentWorkEntry["latest_run"]): string | null {
  if (!run) {
    return null;
  }
  const parts = [`$${run.cost_usd.toFixed(2)}`];
  if (run.tokens > 0) {
    parts.push(`${run.tokens.toLocaleString()} tokens`);
  }
  if (run.approvals || run.rejections) {
    parts.push(`${run.approvals} approved / ${run.rejections} rejected`);
  }
  return parts.join(" · ");
}

/**
 * The work the orchestrator owns: what is queued, what an agent is doing now,
 * and what actually finished. Cancel and retry act on real orchestrator state;
 * the panel never shows progress the queue has not recorded.
 */
export function WorkPanel() {
  const { pushToast, focusedSubject } = useStudio();
  const [items, setItems] = useState<AgentWorkEntry[]>([]);
  const [status, setStatus] = useState<OrchestratorStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [work, orchestrator] = await Promise.all([
        listWorkItems(),
        getOrchestratorStatus(),
      ]);
      setItems(work.work_items);
      setStatus(orchestrator.status);
      setError(null);
    } catch (caught) {
      setError((caught as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function handleCancel(entry: AgentWorkEntry) {
    setBusyId(entry.work_item.id);
    try {
      await cancelWorkItem(entry.work_item.id);
      pushToast("success", `Cancelled “${entry.work_item.title}”.`);
      await refresh();
    } catch (caught) {
      pushToast("error", `Could not cancel: ${(caught as Error).message}`);
    } finally {
      setBusyId(null);
    }
  }

  async function handleRetry(entry: AgentWorkEntry) {
    setBusyId(entry.work_item.id);
    try {
      await retryWorkItem(entry.work_item.id);
      pushToast("success", `Requeued “${entry.work_item.title}” for the daemon.`);
      await refresh();
    } catch (caught) {
      pushToast("error", `Could not retry: ${(caught as Error).message}`);
    } finally {
      setBusyId(null);
    }
  }

  const focusedId = focusedSubject?.kind === "agent_work" ? focusedSubject.id : null;

  return (
    <div className="stack">
      <section className="card" aria-label="Orchestrator status">
        <div className="card__head">
          <span className="card__id">OpenHands autopilot</span>
          <span className={status?.daemon_running ? "badge badge--green" : "badge"}>
            {status?.daemon_running ? "daemon running" : "daemon not running"}
          </span>
          <button type="button" className="quiet-action" onClick={() => void refresh()}>
            Refresh
          </button>
        </div>
        {status ? (
          <>
            <p className="card__meta">
              Queue: {status.queued} queued · {status.running} running ·{" "}
              {status.waiting_for_confirmation} waiting on confirmation
            </p>
            <p className="card__meta">
              Finished: {status.completed} completed · {status.failed} failed · {status.blocked}{" "}
              blocked · {status.cancelled} cancelled
            </p>
            <p className="card__meta">
              Targets: {status.targets.join(", ") || "none configured"}
            </p>
            {!status.daemon_running ? (
              <p className="card__evidence">
                Nothing dispatches while the daemon is stopped. Start it with{" "}
                <code>odi orchestrate start</code>; queued work stays readable meanwhile.
              </p>
            ) : null}
          </>
        ) : (
          <p className="card__meta">Status unavailable.</p>
        )}
      </section>

      {error ? <p className="empty-note">Could not load work: {error}</p> : null}

      {loading ? (
        <p className="empty-note">Reading the orchestrator store…</p>
      ) : items.length === 0 ? (
        <p className="empty-note">
          No work yet. Queue it with <code>odi orchestrate add</code> or ask the assistant to
          delegate a task.
        </p>
      ) : (
        <div className="stack">
          {items.map((entry) => {
            const work = entry.work_item;
            const run = entry.latest_run;
            const active = ACTIVE.includes(work.status);
            const cost = costLabel(run);
            return (
              <article
                key={work.id}
                className={`card${focusedId === work.id ? " card--focused" : ""}`}
              >
                <div className="card__head">
                  <span className="card__id">{work.title}</span>
                  <span className={STATUS_TONE[work.status]}>{statusLabel(work.status)}</span>
                </div>
                <p className="card__meta">
                  {work.source_kind} · agent {work.target_alias} · {work.repository || "no repo"} ·{" "}
                  {work.branch || "default branch"}
                </p>
                {run ? (
                  <p className="card__meta">
                    {run.status}
                    {cost ? ` · ${cost}` : ""}
                    {run.attempt > 1 ? ` · attempt ${run.attempt}` : ""}
                  </p>
                ) : (
                  <p className="card__meta">No run yet; the daemon has not dispatched this.</p>
                )}
                {run?.summary ? <p className="card__evidence">{run.summary}</p> : null}
                {run?.error ? <p className="card__evidence">Error: {run.error}</p> : null}
                {run?.blocked_reason ? (
                  <p className="card__evidence">Blocked: {run.blocked_reason}</p>
                ) : null}
                {run?.pr_urls.length ? (
                  <p className="card__meta">
                    Pull request:{" "}
                    {run.pr_urls.map((url) => (
                      <a key={url} href={url} target="_blank" rel="noreferrer">
                        {url}
                      </a>
                    ))}
                  </p>
                ) : null}
                {run?.conversation_url ? (
                  <p className="card__meta">
                    <a href={run.conversation_url} target="_blank" rel="noreferrer">
                      Open the conversation
                    </a>
                  </p>
                ) : null}
                <div className="card__actions">
                  {active ? (
                    <button
                      type="button"
                      className="quiet-action quiet-action--danger"
                      disabled={busyId === work.id}
                      onClick={() => void handleCancel(entry)}
                    >
                      Cancel
                    </button>
                  ) : (
                    <button
                      type="button"
                      className="quiet-action"
                      disabled={busyId === work.id}
                      onClick={() => void handleRetry(entry)}
                    >
                      Retry
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
