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
    <form onSubmit={submit} className="form">
      <div className="field">
        <label htmlFor="dc-job">Job</label>
        <select
          id="dc-job"
          className="select"
          value={activeJobId}
          onChange={(event) => setJobId(event.target.value)}
        >
          {jobs.length ? (
            jobs.map((job) => (
              <option key={job.id} value={job.id}>
                {job.id}: {job.name ?? ""}
              </option>
            ))
          ) : (
            <option value="">No job yet</option>
          )}
        </select>
      </div>

      <div className="field">
        <label htmlFor="dc-statement">Desired outcome</label>
        <input
          id="dc-statement"
          className="input"
          placeholder="Minimize the time it takes to…"
          value={statement}
          onChange={(event) => setStatement(event.target.value)}
        />
        <p className="field__hint">
          Direction + unit of measure + object of control + contextual clarifier.
        </p>
      </div>

      <div className="field">
        <label htmlFor="dc-importance">Importance · {importance.toFixed(1)}</label>
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

      <div className="field">
        <label htmlFor="dc-satisfaction">Current satisfaction · {satisfaction.toFixed(1)}</label>
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

      <p className="score-preview">
        Opportunity <b>{calcOpp.toFixed(2)}</b>
        <span>{isUnderserved(calcOpp) ? "underserved" : "appropriately served"}</span>
      </p>

      <button
        type="submit"
        className="button button--block"
        disabled={busy || !statement.trim() || !activeJobId}
      >
        Record outcome
      </button>
    </form>
  );
}
