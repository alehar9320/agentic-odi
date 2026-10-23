import { useState, type FormEvent } from "react";
import {
  cancelScheduledWork as apiCancelScheduledWork,
  scheduleWork as apiScheduleWork,
  triggerScheduledWork as apiTriggerScheduledWork,
} from "../../api/studioApi";
import { useStudio } from "../../state/StudioContext";

export function SchedulePanel() {
  const { canvas, settings, pushToast, refreshCanvas } = useStudio();
  const [name, setName] = useState("");
  const [expression, setExpression] = useState("+1h");
  const [agentId, setAgentId] = useState("cloud-agent-1");
  const [triggerType, setTriggerType] = useState<"oneshot" | "cron" | "interval">("oneshot");
  const [selectedJobId, setSelectedJobId] = useState<string>("");
  const [submitting, setSubmitting] = useState(false);

  const scheduledWork = canvas?.scheduled_work ?? [];
  const jobs = canvas?.jobs ?? [];

  async function handleSchedule(e: FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setSubmitting(true);
    try {
      await apiScheduleWork({
        name: name.trim(),
        schedule_expression: expression.trim(),
        agent_id: agentId.trim() || "cloud-agent-1",
        trigger_type: triggerType,
        job_id: selectedJobId || undefined,
        mcp_url: settings.mcp_url,
      });
      pushToast("success", `Scheduled task '${name.trim()}' created!`);
      setName("");
      await refreshCanvas();
    } catch (err) {
      pushToast("error", `Scheduling failed: ${(err as Error).message}`);
    } finally {
      setSubmitting(false);
    }
  }

  async function handleTrigger(workId: string, taskName: string) {
    try {
      await apiTriggerScheduledWork(workId, settings.mcp_url);
      pushToast("success", `Triggered task '${taskName}'!`);
      await refreshCanvas();
    } catch (err) {
      pushToast("error", `Trigger failed: ${(err as Error).message}`);
    }
  }

  async function handleCancel(workId: string, taskName: string) {
    try {
      await apiCancelScheduledWork(workId, settings.mcp_url);
      pushToast("success", `Cancelled task '${taskName}'!`);
      await refreshCanvas();
    } catch (err) {
      pushToast("error", `Cancel failed: ${(err as Error).message}`);
    }
  }

  return (
    <div className="space-y-6 text-slate-100">
      <form onSubmit={handleSchedule} className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 space-y-4">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-teal-400">
          Schedule Cloud Agent Work
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-medium text-slate-400 mb-1">Task Name</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Nightly ODI Opportunity Audit"
              required
              className="w-full px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-sm text-slate-100 focus:outline-none focus:border-teal-500"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-400 mb-1">Schedule Expression</label>
            <input
              type="text"
              value={expression}
              onChange={(e) => setExpression(e.target.value)}
              placeholder="e.g. +1h or 0 0 * * *"
              required
              className="w-full px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-sm text-slate-100 focus:outline-none focus:border-teal-500"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-400 mb-1">Agent ID / Alias</label>
            <input
              type="text"
              value={agentId}
              onChange={(e) => setAgentId(e.target.value)}
              className="w-full px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-sm text-slate-100 focus:outline-none focus:border-teal-500"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-400 mb-1">Trigger Type</label>
            <select
              value={triggerType}
              onChange={(e) => setTriggerType(e.target.value as "oneshot" | "cron" | "interval")}
              className="w-full px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-sm text-slate-100 focus:outline-none focus:border-teal-500"
            >
              <option value="oneshot">oneshot (+delay or ISO)</option>
              <option value="cron">cron (e.g. 0 * * * *)</option>
              <option value="interval">interval</option>
            </select>
          </div>
          {jobs.length > 0 && (
            <div className="md:col-span-2">
              <label className="block text-xs font-medium text-slate-400 mb-1">Associated Job (Optional)</label>
              <select
                value={selectedJobId}
                onChange={(e) => setSelectedJobId(e.target.value)}
                className="w-full px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-sm text-slate-100 focus:outline-none focus:border-teal-500"
              >
                <option value="">-- None --</option>
                {jobs.map((j) => (
                  <option key={j.id} value={j.id}>
                    {j.name || j.id}
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>
        <button
          type="submit"
          disabled={submitting}
          className="px-4 py-2 rounded-lg bg-teal-600 hover:bg-teal-500 disabled:opacity-50 text-sm font-medium transition"
        >
          {submitting ? "Scheduling..." : "Schedule Work"}
        </button>
      </form>

      <div className="space-y-3">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-400">
          Scheduled Tasks ({scheduledWork.length})
        </h3>
        {scheduledWork.length === 0 ? (
          <p className="text-sm text-slate-500 italic">No cloud agent work scheduled yet.</p>
        ) : (
          <div className="grid grid-cols-1 gap-3">
            {scheduledWork.map((task) => (
              <div
                key={task.id}
                className="p-4 rounded-xl bg-slate-900/40 border border-slate-800/80 flex flex-col md:flex-row md:items-center justify-between gap-4"
              >
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-slate-200">{task.name}</span>
                    <span
                      className={`text-[10px] uppercase font-bold px-2 py-0.5 rounded-full ${
                        task.status === "completed"
                          ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                          : task.status === "cancelled"
                            ? "bg-rose-500/20 text-rose-400 border border-rose-500/30"
                            : "bg-amber-500/20 text-amber-400 border border-amber-500/30"
                      }`}
                    >
                      {task.status}
                    </span>
                  </div>
                  <div className="text-xs text-slate-400 mt-1 space-x-3">
                    <span>Agent: {task.agent_id}</span>
                    <span>Type: {task.trigger_type}</span>
                    <span>Expr: {task.schedule_expression}</span>
                  </div>
                  {task.result_summary && (
                    <p className="text-xs text-teal-300 mt-2 bg-slate-950/60 p-2 rounded border border-slate-800">
                      {task.result_summary}
                    </p>
                  )}
                </div>
                <div className="flex items-center gap-2 self-start md:self-center">
                  {task.status !== "completed" && task.status !== "cancelled" && (
                    <>
                      <button
                        onClick={() => handleTrigger(task.id, task.name)}
                        className="px-3 py-1 rounded bg-teal-600/80 hover:bg-teal-500 text-xs font-medium transition"
                      >
                        Trigger
                      </button>
                      <button
                        onClick={() => handleCancel(task.id, task.name)}
                        className="px-3 py-1 rounded bg-rose-900/40 hover:bg-rose-800/60 text-rose-300 text-xs font-medium transition"
                      >
                        Cancel
                      </button>
                    </>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
