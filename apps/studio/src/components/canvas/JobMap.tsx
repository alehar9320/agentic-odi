import { useMemo, useState } from "react";

import { useStudio } from "../../state/StudioContext";
import { FailurePanel } from "../FailurePanel";
import { GhostJobSteps } from "../Skeletons";

// Ulwick Universal Job Process Phases (8 phases)
const UNIVERSAL_PHASES = [
  { id: "define", name: "1. Define", desc: "Determine goals and criteria" },
  { id: "locate", name: "2. Locate", desc: "Gather inputs and resources" },
  { id: "prepare", name: "3. Prepare", desc: "Set up context and workspace" },
  { id: "confirm", name: "4. Confirm", desc: "Verify readiness to execute" },
  { id: "execute", name: "5. Execute", desc: "Carry out core job work" },
  { id: "monitor", name: "6. Monitor", desc: "Track performance and errors" },
  { id: "modify", name: "7. Modify", desc: "Adjust inputs or workflows" },
  { id: "conclude", name: "8. Conclude", desc: "Finish and store outputs" },
];

/** Spread any number of steps across the eight phases, wrapping by order. */
function phaseIndexFor(order: number, stepCount: number): number {
  return Math.min(Math.max(Math.floor(((order - 1) / Math.max(stepCount, 8)) * 8), 0), 7);
}

export function JobMap() {
  const { canvasState, refreshCanvas, updateStep, deleteStep, updateJob, deleteJob } = useStudio();
  const canvas = canvasState.data;
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [editingStepId, setEditingStepId] = useState<string | null>(null);
  const [editStepName, setEditStepName] = useState("");
  const [editStepOrder, setEditStepOrder] = useState(1);
  const [jobName, setJobName] = useState("");
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [busy, setBusy] = useState(false);
  const [selectedPhaseIndex, setSelectedPhaseIndex] = useState<number | null>(null);

  const jobs = canvas?.jobs ?? [];
  const activeJob = jobs.find((job) => job.id === selectedJobId) ?? jobs[0];
  const activeJobId = activeJob?.id ?? "";
  const steps = (canvas?.steps ?? []).filter(
    (step) => !activeJobId || !step.job_id || step.job_id === activeJobId,
  );
  async function saveStep(stepId: string) {
    if (!editStepName.trim()) {
      return;
    }
    setBusy(true);
    try {
      await updateStep(stepId, { name: editStepName.trim(), order: editStepOrder });
      setEditingStepId(null);
    } finally {
      setBusy(false);
    }
  }

  async function saveJob(event: React.FormEvent) {
    event.preventDefault();
    if (!activeJobId || !jobName.trim()) {
      return;
    }
    setBusy(true);
    try {
      await updateJob(activeJobId, { name: jobName.trim() });
      setJobName("");
    } finally {
      setBusy(false);
    }
  }

  // Map steps to 8 phases evenly or by order
  const stepPhaseMapping = useMemo(() => {
    const buckets: Array<{ phase: (typeof UNIVERSAL_PHASES)[0]; steps: typeof steps }> =
      UNIVERSAL_PHASES.map((phase) => ({ phase, steps: [] }));

    steps.forEach((step, idx) => {
      const order = step.order ?? idx + 1;
      buckets[phaseIndexFor(order, steps.length)].steps.push(step);
    });

    return buckets;
  }, [steps]);

  const visibleSteps =
    selectedPhaseIndex === null
      ? steps
      : steps.filter((step, idx) => {
          const order = step.order ?? idx + 1;
          return phaseIndexFor(order, steps.length) === selectedPhaseIndex;
        });

  return (
    <section className="fade-in">
      <p className="section-title">Universal Job Map (8 Process Phases)</p>
      <p className="caption">
        Ulwick Universal Job Steps: Deconstruct human execution into 8 predictable phases to uncover
        latent friction.
      </p>

      {jobs.length > 1 && (
        <div className="field">
          <label htmlFor="jm-job">Job</label>
          <select
            id="jm-job"
            className="select"
            value={activeJobId}
            onChange={(event) => {
              setSelectedJobId(event.target.value);
              setEditingStepId(null);
            }}
          >
            {jobs.map((job) => (
              <option key={job.id} value={job.id}>
                {job.id}: {job.name ?? "Untitled job"}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Visual Phase Pipeline Flow */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))",
          gap: 8,
          marginTop: 16,
          marginBottom: 20,
        }}
      >
        {UNIVERSAL_PHASES.map((phase, idx) => {
          const bucket = stepPhaseMapping[idx];
          const hasSteps = bucket.steps.length > 0;
          const isSelected = selectedPhaseIndex === idx;

          return (
            <div
              key={phase.id}
              onClick={() => setSelectedPhaseIndex(isSelected ? null : idx)}
              style={{
                background: isSelected
                  ? "rgba(129, 140, 248, 0.2)"
                  : hasSteps
                    ? "rgba(255, 255, 255, 0.04)"
                    : "rgba(255, 255, 255, 0.01)",
                border: isSelected
                  ? "1px solid var(--studio-indigo)"
                  : hasSteps
                    ? "1px solid var(--studio-border)"
                    : "1px dashed rgba(255, 255, 255, 0.05)",
                borderRadius: 8,
                padding: "10px 12px",
                cursor: "pointer",
                transition: "all 0.2s ease",
                position: "relative",
              }}
            >
              <div
                style={{
                  fontSize: "0.78rem",
                  fontWeight: 700,
                  color: hasSteps ? "var(--studio-text)" : "var(--studio-muted)",
                }}
              >
                {phase.name}
              </div>
              <div
                style={{
                  fontSize: "0.7rem",
                  color: "var(--studio-muted)",
                  marginTop: 2,
                  height: 28,
                  overflow: "hidden",
                }}
              >
                {phase.desc}
              </div>
              <div
                style={{
                  marginTop: 8,
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                }}
              >
                <span
                  className="studio-pill"
                  style={{
                    fontSize: "0.68rem",
                    padding: "2px 6px",
                    background: hasSteps ? "rgba(129, 140, 248, 0.15)" : "transparent",
                    color: hasSteps ? "var(--studio-indigo)" : "rgba(255,255,255,0.2)",
                  }}
                >
                  {bucket.steps.length} {bucket.steps.length === 1 ? "step" : "steps"}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {canvasState.kind === "error" ? (
        <FailurePanel
          error={canvasState.error}
          onRetry={() => void refreshCanvas()}
          retryText="reload"
        />
      ) : canvasState.kind === "loading" ? (
        <GhostJobSteps />
      ) : steps.length ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {visibleSteps.map((step) => {
            const index = steps.indexOf(step);
            const order = step.order ?? index + 1;

            return (
              <div
                className="step-row fade-in"
                key={step.id ?? index}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  gap: 12,
                  background: "var(--studio-surface)",
                  border: "1px solid var(--studio-border)",
                  borderRadius: 8,
                  padding: "10px 14px",
                }}
              >
                {editingStepId === step.id ? (
                  <div className="step__edit">
                    <input
                      className="input"
                      aria-label={`Step ${index + 1} name`}
                      value={editStepName}
                      onChange={(event) => setEditStepName(event.target.value)}
                    />
                    <input
                      className="input input--order"
                      type="number"
                      min={1}
                      max={20}
                      aria-label={`Step ${index + 1} position`}
                      value={editStepOrder}
                      onChange={(event) => setEditStepOrder(Number(event.target.value))}
                    />
                    <button
                      type="button"
                      className="quiet-action"
                      disabled={busy}
                      onClick={() => void saveStep(step.id ?? "")}
                    >
                      Save
                    </button>
                    <button
                      type="button"
                      className="quiet-action"
                      onClick={() => setEditingStepId(null)}
                    >
                      Cancel
                    </button>
                  </div>
                ) : (
                  <>
                    <div>
                      <span
                        style={{ color: "var(--studio-indigo)", fontWeight: 700, marginRight: 8 }}
                      >
                        Step {order}
                      </span>
                      <span style={{ color: "var(--studio-text)" }}>{step.name ?? ""}</span>
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <span
                        style={{
                          fontSize: "0.78rem",
                          color: "var(--studio-muted)",
                          fontStyle: "italic",
                        }}
                      >
                        Phase {phaseIndexFor(order, steps.length) + 1}
                      </span>
                      {step.id && (
                        <span className="step__actions">
                          <button
                            type="button"
                            className="quiet-action"
                            onClick={() => {
                              setEditingStepId(step.id ?? null);
                              setEditStepName(step.name ?? "");
                              setEditStepOrder(order);
                            }}
                          >
                            Edit
                          </button>
                          <button
                            type="button"
                            className="quiet-action"
                            disabled={busy}
                            onClick={() => void deleteStep(step.id ?? "")}
                          >
                            Remove
                          </button>
                        </span>
                      )}
                    </div>
                  </>
                )}
              </div>
            );
          })}
        </div>
      ) : (
        <p className="toast toast--info" role="status">
          {selectedPhaseIndex === null
            ? "No steps captured yet. Ask the studio to walk you through the job."
            : "No steps land in this phase yet."}
        </p>
      )}

      {activeJobId && (
        <details className="disclosure" style={{ marginTop: 12 }}>
          <summary>Manage this job</summary>
          <form onSubmit={saveJob} className="form">
            <div className="field">
              <label htmlFor="jm-rename">Rename job</label>
              <input
                id="jm-rename"
                className="input"
                placeholder={activeJob?.name ?? "Job name"}
                value={jobName}
                onChange={(event) => setJobName(event.target.value)}
              />
            </div>
            <button type="submit" className="button button--ghost" disabled={busy || !jobName.trim()}>
              Save name
            </button>
          </form>
          <div className="settings__actions">
            <button
              type="button"
              className="button button--danger"
              disabled={busy}
              onClick={() => {
                if (!confirmDelete) {
                  setConfirmDelete(true);
                  return;
                }
                setConfirmDelete(false);
                void deleteJob(activeJobId);
              }}
            >
              {confirmDelete ? "Confirm delete job" : "Delete job"}
            </button>
          </div>
        </details>
      )}
    </section>
  );
}
