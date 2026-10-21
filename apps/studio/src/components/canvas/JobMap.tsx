import { useMemo, useState } from "react";

import { useStudio } from "../../state/StudioContext";
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

export function JobMap() {
  const { canvas, canvasLoading, addStep } = useStudio();
  const [stepName, setStepName] = useState("");
  const [stepOrder, setStepOrder] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [selectedPhaseIndex, setSelectedPhaseIndex] = useState<number | null>(null);

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

  // Map steps to 8 phases evenly or by order
  const stepPhaseMapping = useMemo(() => {
    const buckets: Array<{ phase: typeof UNIVERSAL_PHASES[0]; steps: typeof steps }> = UNIVERSAL_PHASES.map((phase) => ({
      phase,
      steps: [],
    }));

    steps.forEach((step, idx) => {
      const order = step.order ?? idx + 1;
      // Distribute 1..8 or wrap around
      const phaseIdx = Math.min(Math.max(Math.floor(((order - 1) / Math.max(steps.length, 8)) * 8), 0), 7);
      buckets[phaseIdx].steps.push(step);
    });

    return buckets;
  }, [steps]);

  return (
    <section className="fade-in">
      <h2 className="section-title">Universal Job Map (8 Process Phases)</h2>
      <p className="caption">
        Ulwick Universal Job Steps: Deconstruct human execution into 8 predictable phases to uncover latent friction.
      </p>

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
              <div style={{ fontSize: "0.78rem", fontWeight: 700, color: hasSteps ? "var(--studio-text)" : "var(--studio-muted)" }}>
                {phase.name}
              </div>
              <div style={{ fontSize: "0.7rem", color: "var(--studio-muted)", marginTop: 2, height: 28, overflow: "hidden" }}>
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

      {canvasLoading && !canvas ? (
        <GhostJobSteps />
      ) : steps.length ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {steps
            .filter((_, idx) => {
              if (selectedPhaseIndex === null) return true;
              const order = steps[idx].order ?? idx + 1;
              const phaseIdx = Math.min(Math.max(Math.floor(((order - 1) / Math.max(steps.length, 8)) * 8), 0), 7);
              return phaseIdx === selectedPhaseIndex;
            })
            .map((step, index) => (
              <div
                className="step-row fade-in"
                key={step.id ?? index}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  background: "var(--studio-surface)",
                  border: "1px solid var(--studio-border)",
                  borderRadius: 8,
                  padding: "10px 14px",
                }}
              >
                <div>
                  <span style={{ color: "var(--studio-indigo)", fontWeight: 700, marginRight: 8 }}>
                    Step {step.order ?? ""}
                  </span>
                  <span style={{ color: "var(--studio-text)" }}>{step.name ?? ""}</span>
                </div>
                <span style={{ fontSize: "0.78rem", color: "var(--studio-muted)", fontStyle: "italic" }}>
                  Phase {Math.min(Math.max(Math.floor((((step.order ?? index + 1) - 1) / Math.max(steps.length, 8)) * 8) + 1, 1), 8)}
                </span>
              </div>
            ))}
        </div>
      ) : (
        <p className="toast toast--info" role="status">
          No job steps registered yet. Ask the AI assistant to decompose the active job!
        </p>
      )}

      <details style={{ marginTop: 18 }}>
        <summary style={{ cursor: "pointer", fontWeight: 600, color: "var(--studio-indigo)" }}>
          ➕ Add Step to Universal Job Map
        </summary>
        <form onSubmit={submit} style={{ marginTop: 12 }}>
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
