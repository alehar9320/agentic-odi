import { useState, type FormEvent } from "react";

import {
  cancelScheduledWork as apiCancelScheduledWork,
  scheduleWork as apiScheduleWork,
  triggerScheduledWork as apiTriggerScheduledWork,
} from "../../api/studioApi";
import { useStudio } from "../../state/StudioContext";
import type { ScheduledWork } from "../../types";

/** The status, as a badge tone. `failed` is a warning, `running` is in flight. */
function statusTone(status: ScheduledWork["status"]): string {
  switch (status) {
    case "completed":
      return "badge badge--green";
    case "running":
      return "badge badge--blue";
    case "failed":
      return "badge badge--amber";
    default:
      return "badge";
  }
}

function formatTime(value: string): string {
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
}

/**
 * Schedule work for an agent and let the daemon dispatch it. The expression is
 * parsed when the schedule is created, so the panel shows the real next run
 * instead of guessing. Trigger queues an occurrence immediately; it never
 * claims the work ran.
 */
export function SchedulePanel({ agentId: initialAgentId }: { agentId?: string }) {
  const { canvas, settings, pushToast, refreshCanvas } = useStudio();
  const [name, setName] = useState("");
  const [expression, setExpression] = useState("");
  const [agentId, setAgentId] = useState(initialAgentId ?? "");
  const [selectedJobId, setSelectedJobId] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const scheduledWork = canvas?.scheduled_work ?? [];
  const jobs = canvas?.jobs ?? [];

  async function handleSchedule(event: FormEvent) {
    event.preventDefault();
    if (!name.trim() || submitting) {
      return;
    }
    setSubmitting(true);
    try {
      await apiScheduleWork({
        name: name.trim(),
        schedule_expression: expression.trim(),
        agent_id: agentId.trim() || "default-agent",
        job_id: selectedJobId || undefined,
        mcp_url: settings.mcp_url,
      });
      pushToast(
        "success",
        `Scheduled “${name.trim()}”. It runs when the orchestrator daemon is running.`,
      );
      setName("");
      setExpression("");
      await refreshCanvas();
    } catch (error) {
      pushToast("error", `Could not schedule: ${(error as Error).message}`);
    } finally {
      setSubmitting(false);
    }
  }

  async function handleTrigger(work: ScheduledWork) {
    try {
      await apiTriggerScheduledWork(work.id, settings.mcp_url);
      pushToast(
        "success",
        `Queued “${work.name}” for the orchestrator; it has not run yet.`,
      );
      await refreshCanvas();
    } catch (error) {
      pushToast("error", `Could not queue: ${(error as Error).message}`);
    }
  }

  async function handleCancel(work: ScheduledWork) {
    try {
      await apiCancelScheduledWork(work.id, settings.mcp_url);
      pushToast("success", `Cancelled “${work.name}”.`);
      await refreshCanvas();
    } catch (error) {
      pushToast("error", `Could not cancel: ${(error as Error).message}`);
    }
  }

  return (
    <div className="stack">
      <form onSubmit={handleSchedule} className="form">
        <div className="field">
          <label htmlFor="schedule-name">What should the agent do?</label>
          <input
            id="schedule-name"
            className="input"
            value={name}
            placeholder="Nightly opportunity audit"
            onChange={(event) => setName(event.target.value)}
          />
        </div>

        <div className="field">
          <label htmlFor="schedule-expression">When</label>
          <input
            id="schedule-expression"
            className="input"
            value={expression}
            placeholder="+1h, 0 0 * * *, or 2026-11-01T09:00Z"
            onChange={(event) => setExpression(event.target.value)}
          />
          <p className="field__hint">
            An ISO timestamp, a relative delay (+90m, +2d), or a cron expression. The expression
            is parsed when you schedule it and decides whether the work runs once or repeatedly.
          </p>
        </div>

        <div className="field">
          <label htmlFor="schedule-agent">
            Agent <span className="field__hint">defaults to default-agent</span>
          </label>
          <input
            id="schedule-agent"
            className="input"
            value={agentId}
            placeholder="default-agent"
            onChange={(event) => setAgentId(event.target.value)}
          />
        </div>

        <div className="field">
          <label htmlFor="schedule-job">
            Job <span className="field__hint">optional</span>
          </label>
          <select
            id="schedule-job"
            className="select"
            value={selectedJobId}
            onChange={(event) => setSelectedJobId(event.target.value)}
          >
            <option value="">No job</option>
            {jobs.map((job) => (
              <option key={job.id} value={job.id}>
                {job.name || job.id}
              </option>
            ))}
          </select>
        </div>

        <button
          type="submit"
          className="button button--block"
          disabled={submitting || !name.trim()}
        >
          {submitting ? "Scheduling…" : "Schedule work"}
        </button>
      </form>

      <p className="section-title">Scheduled ({scheduledWork.length})</p>
      {scheduledWork.length === 0 ? (
        <p className="empty-note">
          Nothing scheduled yet. The orchestrator daemon turns due schedules into agent work.
        </p>
      ) : (
        <div className="stack">
          {scheduledWork.map((work) => (
            <article key={work.id} className="card">
              <div className="card__head">
                <span className="card__id">{work.name}</span>
                <span className={statusTone(work.status)}>{work.status}</span>
              </div>
              <p className="card__meta">
                Agent {work.agent_id} · {work.trigger_type} · {work.schedule_expression || "—"}
              </p>
              <p className="card__meta">
                {work.trigger_requested_at
                  ? `Queued for the orchestrator ${formatTime(work.trigger_requested_at)}`
                  : work.next_run_at
                    ? `Next run ${formatTime(work.next_run_at)}`
                    : "No next run; one-shot work runs once when queued"}
                {work.last_run_at ? ` · Last run ${formatTime(work.last_run_at)}` : ""}
              </p>
              {work.result_summary ? <p className="card__evidence">{work.result_summary}</p> : null}
              {work.status !== "cancelled" && work.status !== "completed" ? (
                <div className="card__actions">
                  <button
                    type="button"
                    className="quiet-action"
                    onClick={() => void handleTrigger(work)}
                  >
                    Queue now
                  </button>
                  <button
                    type="button"
                    className="quiet-action quiet-action--danger"
                    onClick={() => void handleCancel(work)}
                  >
                    Cancel
                  </button>
                </div>
              ) : null}
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
