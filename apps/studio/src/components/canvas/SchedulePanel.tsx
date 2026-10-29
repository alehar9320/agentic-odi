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

/**
 * The scheduling foundation: record work for an agent, dispatch it, or cancel
 * it. No executor is installed yet (#95), so Trigger records a dispatch and
 * says so; it never claims the work ran. The agent id arrives as data.
 */
export function SchedulePanel({ agentId: initialAgentId }: { agentId?: string }) {
  const { canvas, settings, pushToast, refreshCanvas } = useStudio();
  const [name, setName] = useState("");
  const [expression, setExpression] = useState("");
  const [agentId, setAgentId] = useState(initialAgentId ?? "");
  const [triggerType, setTriggerType] = useState<"oneshot" | "cron" | "interval">("oneshot");
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
        trigger_type: triggerType,
        job_id: selectedJobId || undefined,
        mcp_url: settings.mcp_url,
      });
      pushToast("success", `Scheduled “${name.trim()}”.`);
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
      pushToast("success", `Dispatched “${work.name}” — no executor is installed yet.`);
      await refreshCanvas();
    } catch (error) {
      pushToast("error", `Could not trigger: ${(error as Error).message}`);
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
          <label htmlFor="schedule-expression">
            When <span className="field__hint">stored verbatim, not parsed yet</span>
          </label>
          <input
            id="schedule-expression"
            className="input"
            value={expression}
            placeholder="+1h, 0 0 * * *, or 2026-11-01T09:00Z"
            onChange={(event) => setExpression(event.target.value)}
          />
          <p className="field__hint">
            Nothing reads this expression yet — no scheduler exists (#95). It is kept so the
            record is complete when one does.
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
          <label htmlFor="schedule-trigger">Trigger type</label>
          <select
            id="schedule-trigger"
            className="select"
            value={triggerType}
            onChange={(event) =>
              setTriggerType(event.target.value as "oneshot" | "cron" | "interval")
            }
          >
            <option value="oneshot">oneshot</option>
            <option value="cron">cron</option>
            <option value="interval">interval</option>
          </select>
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
        <p className="empty-note">Nothing scheduled yet. There is no executor, so nothing runs.</p>
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
              {work.result_summary ? <p className="card__evidence">{work.result_summary}</p> : null}
              {work.status !== "cancelled" && work.status !== "completed" ? (
                <div className="card__actions">
                  <button
                    type="button"
                    className="quiet-action"
                    onClick={() => void handleTrigger(work)}
                  >
                    Dispatch
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
