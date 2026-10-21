import { useState } from "react";

import { useStudio } from "../../state/StudioContext";
import { GhostJobSteps } from "../Skeletons";

export function JobMap() {
  const { canvas, canvasLoading, addStep } = useStudio();
  const [stepName, setStepName] = useState("");
  const [stepOrder, setStepOrder] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);

  const steps = canvas?.steps ?? [];
  const jobs = canvas?.jobs ?? [];
  const activeJobId = jobs[0]?.id ?? "JOB-402";
  const defaultOrder = steps.length + 1;

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!stepName.trim() || busy) {
      return;
    }
    setBusy(true);
    try {
      await addStep({ job_id: activeJobId, name: stepName.trim(), order: stepOrder ?? defaultOrder });
      setStepName("");
      setStepOrder(null);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section>
      <h2 className="section-title">Universal Job Map (8 Process Phases)</h2>
      <p className="caption">
        Ulwick Universal Job Steps: Define ➔ Locate ➔ Prepare ➔ Confirm ➔ Execute ➔ Monitor ➔ Modify ➔ Conclude
      </p>

      {canvasLoading && !canvas ? (
        <GhostJobSteps />
      ) : steps.length ? (
        steps.map((step, index) => (
          <div className="step-row fade-in" key={step.id ?? index}>
            <b>Step {step.order ?? ""}</b>: {step.name ?? ""}
          </div>
        ))
      ) : (
        <p className="toast toast--info" role="status">
          No job steps registered yet. Ask the AI assistant to decompose the active job.
        </p>
      )}

      <details style={{ marginTop: 14 }}>
        <summary style={{ cursor: "pointer" }}>➕ Add Step to Job Map</summary>
        <form onSubmit={submit} style={{ marginTop: 10 }}>
          <div className="studio-field">
            <label htmlFor="step-name">Step Description (e.g., &apos;3. Prepare secrets payload&apos;)</label>
            <input
              id="step-name"
              className="studio-input"
              value={stepName}
              onChange={(event) => setStepName(event.target.value)}
            />
          </div>
          <div className="studio-field">
            <label htmlFor="step-order">Step Chronological Order</label>
            <input
              id="step-order"
              className="studio-input"
              type="number"
              min={1}
              max={20}
              value={stepOrder ?? defaultOrder}
              onChange={(event) => setStepOrder(Number(event.target.value))}
            />
          </div>
          <button type="submit" className="studio-button" disabled={busy || !stepName.trim()}>
            Add Step to Map
          </button>
        </form>
      </details>
    </section>
  );
}
