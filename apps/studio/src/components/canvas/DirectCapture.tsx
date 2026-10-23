import { useMemo, useState } from "react";

import { isUnderserved, opportunityScore } from "../../lib/odi";
import { useStudio } from "../../state/StudioContext";

export function DirectCapture() {
  const { canvas, addOutcome } = useStudio();
  const jobs = canvas?.jobs ?? [];

  const [jobId, setJobId] = useState<string | null>(null);
  const [statement, setStatement] = useState("");
  const [importance, setImportance] = useState(8.5);
  const [satisfaction, setSatisfaction] = useState(3.5);
  const [busy, setBusy] = useState(false);

  const activeJobId = jobId ?? jobs[0]?.id ?? "";

  const calcOpp = useMemo(
    () => opportunityScore(importance, satisfaction),
    [importance, satisfaction],
  );

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!statement.trim() || !activeJobId || busy) {
      return;
    }
    setBusy(true);
    try {
      await addOutcome({
        job_id: activeJobId,
        statement: statement.trim(),
        importance,
        satisfaction,
      });
      setStatement("");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section>
      <h2 className="section-title">Direct Capture: Jobs &amp; Outcomes</h2>
      <p className="caption">
        Prefer direct entry over conversational typing? Add artifacts directly to the MCP
        repository.
      </p>

      <form onSubmit={submit}>
        <div className="studio-field">
          <label htmlFor="dc-job">Select Job</label>
          <select
            id="dc-job"
            className="studio-select"
            value={activeJobId}
            onChange={(event) => setJobId(event.target.value)}
          >
            {jobs.map((job) => (
              <option key={job.id} value={job.id}>
                {job.id}: {job.name ?? ""}
              </option>
            ))}
          </select>
        </div>

        <div className="studio-field">
          <label htmlFor="dc-statement">Desired Outcome Statement</label>
          <input
            id="dc-statement"
            className="studio-input"
            placeholder="Minimize the time it takes to..."
            value={statement}
            onChange={(event) => setStatement(event.target.value)}
          />
          <p className="caption" style={{ marginTop: 4 }}>
            Format: [Direction] + [Unit of Measure] + [Object of Control] + [Contextual Clarifier]
          </p>
        </div>

        <div className="studio-form-grid">
          <div className="studio-field">
            <label htmlFor="dc-importance">Importance Score (1-10): {importance.toFixed(1)}</label>
            <input
              id="dc-importance"
              type="range"
              min={1}
              max={10}
              step={0.1}
              value={importance}
              onChange={(event) => setImportance(Number(event.target.value))}
            />
          </div>
          <div className="studio-field">
            <label htmlFor="dc-satisfaction">
              Current Satisfaction (1-10): {satisfaction.toFixed(1)}
            </label>
            <input
              id="dc-satisfaction"
              type="range"
              min={1}
              max={10}
              step={0.1}
              value={satisfaction}
              onChange={(event) => setSatisfaction(Number(event.target.value))}
            />
          </div>
        </div>

        <p className="toast toast--info" role="status" style={{ marginBottom: 12 }}>
          📊 <b>Calculated Opportunity Score</b>: <code>{calcOpp.toFixed(2)}</code> (
          {isUnderserved(calcOpp) ? "🔥 Underserved" : "Appropriately Served"})
        </p>

        <button type="submit" className="studio-button" disabled={busy || !statement.trim()}>
          Record Desired Outcome
        </button>
      </form>
    </section>
  );
}
