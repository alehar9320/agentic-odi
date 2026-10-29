import { useMemo, useState } from "react";

import { isUnderserved, opportunityScore } from "../../lib/odi";
import { useStudio } from "../../state/StudioContext";

export function DirectCapture() {
  const { canvas, addOutcome, createJob } = useStudio();
  const jobs = canvas?.jobs ?? [];

  const [jobId, setJobId] = useState<string | null>(null);
  const [jobName, setJobName] = useState("");
  const [jobDescription, setJobDescription] = useState("");
  const [creatingJob, setCreatingJob] = useState(false);
  const [statement, setStatement] = useState("");
  const [importance, setImportance] = useState(8.5);
  const [satisfaction, setSatisfaction] = useState(3.5);
  const [busy, setBusy] = useState(false);

  const activeJobId = jobId ?? jobs[0]?.id ?? "";

  const calcOpp = useMemo(
    () => opportunityScore(importance, satisfaction),
    [importance, satisfaction],
  );

  async function createNewJob(event: React.FormEvent) {
    event.preventDefault();
    if (!jobName.trim() || creatingJob) {
      return;
    }
    setCreatingJob(true);
    try {
      const id = await createJob({
        name: jobName.trim(),
        description: jobDescription.trim() || undefined,
      });
      if (id) {
        setJobId(id);
      }
      setJobName("");
      setJobDescription("");
    } finally {
      setCreatingJob(false);
    }
  }

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
    <div className="stack">
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
          {!jobs.length && (
            <p className="field__hint">
              Add the job below first — an outcome is always a metric for a job.
            </p>
          )}
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

      <details className="disclosure" open={!jobs.length}>
        <summary>Add a job</summary>
        <form onSubmit={createNewJob} className="form">
          <div className="field">
            <label htmlFor="dc-new-job">Job name</label>
            <input
              id="dc-new-job"
              className="input"
              placeholder="Get a service from commit to production"
              value={jobName}
              onChange={(event) => setJobName(event.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="dc-new-job-desc">
              Who is doing it? <span className="field__hint">optional</span>
            </label>
            <input
              id="dc-new-job-desc"
              className="input"
              placeholder="Platform engineers shipping services"
              value={jobDescription}
              onChange={(event) => setJobDescription(event.target.value)}
            />
          </div>
          <button
            type="submit"
            className="button button--ghost"
            disabled={creatingJob || !jobName.trim()}
          >
            {creatingJob ? "Adding…" : "Add job"}
          </button>
        </form>
      </details>
    </div>
  );
}
