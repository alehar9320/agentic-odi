import { useState } from "react";

import { useStudio } from "../../state/StudioContext";
import type { JobStageDef } from "../../types";
import { FailurePanel } from "../FailurePanel";
import { GhostJobSteps } from "../Skeletons";

/** The stage a step belongs to, by its id, or null when it names none. */
function stageIndexOf(stepStage: string | null | undefined, stages: JobStageDef[]): number | null {
  if (!stepStage) {
    return null;
  }
  const index = stages.findIndex((stage) => stage.id === stepStage);
  return index === -1 ? null : index;
}

/**
 * Spread a stage-less step across the given stages by order. Legacy steps
 * predate the stage field, so their position is the only honest signal; a step
 * that names a stage is placed by that stage instead.
 */
function phaseIndexFor(order: number, stepCount: number, stageCount: number): number {
  if (stageCount <= 0) {
    return 0;
  }
  return Math.min(
    Math.max(Math.floor(((order - 1) / Math.max(stepCount, stageCount)) * stageCount), 0),
    stageCount - 1,
  );
}

export function JobMap() {
  const {
    canvasState,
    stagesState,
    refreshStages,
    refreshCanvas,
    addStep,
    updateStep,
    deleteStep,
    updateJob,
    deleteJob,
    focusedJobId,
  } = useStudio();
  const canvas = canvasState.data;
  const stages = stagesState.data ?? [];
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [editingStepId, setEditingStepId] = useState<string | null>(null);
  const [focusedStepId, setFocusedStepId] = useState<string | null>(null);
  const [editStepName, setEditStepName] = useState("");
  const [editStepOrder, setEditStepOrder] = useState(1);
  const [jobName, setJobName] = useState("");
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [busy, setBusy] = useState(false);
  const [selectedPhaseIndex, setSelectedPhaseIndex] = useState<number | null>(null);
  const [addStepOpen, setAddStepOpen] = useState(false);
  const [newStepName, setNewStepName] = useState("");
  const [followedJobId, setFollowedJobId] = useState<string | null>(null);

  const jobs = canvas?.jobs ?? [];
  // A signal names the job it is about. Follow it until the person picks a job
  // themselves, so the map never fights with an explicit choice.
  const focusedJob =
    focusedJobId && focusedJobId !== followedJobId
      ? jobs.find((job) => job.id === focusedJobId)
      : undefined;
  const activeJob = focusedJob ?? jobs.find((job) => job.id === selectedJobId) ?? jobs[0];
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

  /** Swap a step with its neighbour, so order changes without a mouse. */
  async function moveStep(stepId: string, direction: -1 | 1) {
    const index = steps.findIndex((step) => step.id === stepId);
    const target = index + direction;
    if (index < 0 || target < 0 || target >= steps.length) {
      return;
    }
    setBusy(true);
    try {
      await updateStep(steps[index].id ?? "", { order: target + 1 });
      await updateStep(steps[target].id ?? "", { order: index + 1 });
    } finally {
      setBusy(false);
    }
  }

  const nextStepOrder =
    steps.reduce((max, step, index) => Math.max(max, step.order ?? index + 1), 0) + 1;

  async function saveNewStep() {
    const name = newStepName.trim();
    if (!activeJobId || !name) {
      return;
    }
    setBusy(true);
    try {
      await addStep({ job_id: activeJobId, name, order: nextStepOrder });
      setNewStepName("");
      setAddStepOpen(false);
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

  // Bucket steps under the stages the server named: a step's own stage when it
  // has one, its order otherwise. Nothing is invented here.
  const stepPhaseMapping = stages.map((stage) => ({ stage, steps: [] as typeof steps }));
  const stepStageIndex = (step: (typeof steps)[number], idx: number): number => {
    const named = stageIndexOf(step.stage, stages);
    if (named !== null) {
      return named;
    }
    const order = step.order ?? idx + 1;
    return phaseIndexFor(order, steps.length, stages.length);
  };
  steps.forEach((step, idx) => {
    const bucket = stepPhaseMapping[stepStageIndex(step, idx)];
    if (bucket) {
      bucket.steps.push(step);
    }
  });

  const visibleSteps =
    selectedPhaseIndex === null
      ? steps
      : steps.filter((step, idx) => stepStageIndex(step, idx) === selectedPhaseIndex);

  if (stagesState.kind === "error") {
    // A failed schema must not render as an empty map: the stages are unknown,
    // so the map names the request that failed instead of inventing eight.
    return (
      <section className="fade-in">
        <p className="section-title">Universal Job Map</p>
        <FailurePanel
          error={stagesState.error}
          onRetry={() => void refreshStages()}
          retryText="reload"
        />
      </section>
    );
  }

  if (canvasState.kind === "error") {
    // A failed canvas must not render as an empty map either.
    return (
      <section className="fade-in">
        <p className="section-title">Universal Job Map</p>
        <FailurePanel
          error={canvasState.error}
          onRetry={() => void refreshCanvas()}
          retryText="reload"
        />
      </section>
    );
  }

  if (stagesState.kind === "loading" && stages.length === 0) {
    return (
      <section className="fade-in">
        <p className="section-title">Universal Job Map</p>
        <p className="caption">Loading the job-map stages…</p>
      </section>
    );
  }

  return (
    <section className="fade-in">
      <p className="section-title">Universal Job Map</p>
      <p className="caption">
        Ulwick Universal Job Steps: deconstruct human execution into the stages of the job to uncover
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
              setFollowedJobId(focusedJobId);
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
        {stepPhaseMapping.map((bucket, idx) => {
          const { stage } = bucket;
          const hasSteps = bucket.steps.length > 0;
          const isSelected = selectedPhaseIndex === idx;

          return (
            <button
              key={stage.id}
              type="button"
              aria-pressed={isSelected}
              aria-label={`Filter steps by ${stage.name}`}
              onClick={() => setSelectedPhaseIndex(isSelected ? null : idx)}
              style={{
                display: "block",
                width: "100%",
                textAlign: "left",
                font: "inherit",
                color: "inherit",
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
              <span
                className="jm-stage__name"
                style={{
                  display: "block",
                  fontSize: "0.78rem",
                  fontWeight: 700,
                  color: hasSteps ? "var(--studio-text)" : "var(--studio-muted)",
                }}
              >
                {stage.name}
              </span>
              <span
                style={{
                  display: "block",
                  fontSize: "0.7rem",
                  color: "var(--studio-muted)",
                  marginTop: 2,
                  height: 28,
                  overflow: "hidden",
                }}
              >
                {stage.description}
              </span>
              <span
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
              </span>
            </button>
          );
        })}
      </div>

      {/* A job has one step per stage: the domain refuses an order past the map. */}
      {activeJobId && stages.length > 0 && steps.length < stages.length && (
        <div className="jm-add">
          {addStepOpen ? (
            <form
              className="form jm-add__form"
              onSubmit={(event) => {
                event.preventDefault();
                void saveNewStep();
              }}
              onKeyDown={(event) => {
                if (event.key === "Escape") {
                  event.preventDefault();
                  setAddStepOpen(false);
                }
              }}
            >
              <div className="field">
                <label htmlFor="jm-new-step">New step name</label>
                <input
                  id="jm-new-step"
                  className="input"
                  autoFocus
                  value={newStepName}
                  onChange={(event) => setNewStepName(event.target.value)}
                />
              </div>
              <div className="step__edit">
                <button
                  type="submit"
                  className="quiet-action"
                  disabled={busy || !newStepName.trim()}
                >
                  Save
                </button>
                <button
                  type="button"
                  className="quiet-action"
                  onClick={() => setAddStepOpen(false)}
                >
                  Cancel
                </button>
              </div>
            </form>
          ) : (
            <button type="button" className="quiet-action" onClick={() => setAddStepOpen(true)}>
              Add step
            </button>
          )}
        </div>
      )}

      {canvasState.kind === "loading" ? (
        <GhostJobSteps />
      ) : steps.length ? (
        <div
          role="list"
          aria-label="Job steps"
          style={{ display: "flex", flexDirection: "column", gap: 8 }}
        >
          {visibleSteps.map((step) => {
            const index = steps.indexOf(step);
            const order = step.order ?? index + 1;

            return (
              <div
                className="step-row fade-in"
                key={step.id ?? index}
                role="listitem"
                tabIndex={0}
                aria-label={`Step ${order}: ${step.name ?? ""}`}
                onFocus={() => setFocusedStepId(step.id ?? null)}
                onBlur={() => setFocusedStepId(null)}
                onKeyDown={(event) => {
                  if (!step.id || busy || editingStepId === step.id) {
                    return;
                  }
                  if (event.key === "ArrowUp") {
                    event.preventDefault();
                    void moveStep(step.id, -1);
                  } else if (event.key === "ArrowDown") {
                    event.preventDefault();
                    void moveStep(step.id, 1);
                  }
                }}
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
                        {stepPhaseMapping[stepStageIndex(step, index)]?.stage.name ?? ""}
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
                          <button
                            type="button"
                            className="quiet-action"
                            disabled={busy || !step.id}
                            aria-label="Move step up"
                            aria-grabbed={focusedStepId === step.id}
                            onClick={() => void moveStep(step.id ?? "", -1)}
                          >
                            Move up
                          </button>
                          <button
                            type="button"
                            className="quiet-action"
                            disabled={busy || !step.id}
                            aria-label="Move step down"
                            aria-grabbed={focusedStepId === step.id}
                            onClick={() => void moveStep(step.id ?? "", 1)}
                          >
                            Move down
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
