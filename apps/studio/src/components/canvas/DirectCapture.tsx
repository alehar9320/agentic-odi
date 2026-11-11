import { useMemo, useState } from "react";

import { asStudioError } from "../../api/studioApi";
import { formatOpportunityScore, isUnderserved, opportunityScore } from "../../lib/odi";
import { useStudio } from "../../state/StudioContext";
import type { StudioError } from "../../types";
import { FailurePanel } from "../FailurePanel";

/** Which field the failure belongs to, so the message lands next to it. */
type FailureField = "statement" | "range" | "form";

/**
 * Where to show a failure. The server names the field when it knows one, so a
 * field-specific failure lands next to the field that needs it; otherwise we
 * fall back to the code-based heuristic and, failing that, the whole form —
 * the best guess we have for a failure that predates the field or came from a
 * peer that only sends text.
 */
function fieldForError(error: StudioError): FailureField {
  if (error.field === "importance" || error.field === "satisfaction") {
    return "range";
  }
  if (error.field === "statement" || error.field === "business_statement") {
    return "statement";
  }
  if (error.code === "out_of_range") {
    return "range";
  }
  return "form";
}

export function DirectCapture() {
  const { canvas, createJob, queueCapture, queuedCaptures, failedCaptures } = useStudio();
  const jobs = canvas?.jobs ?? [];

  const [jobId, setJobId] = useState<string | null>(null);
  const [jobName, setJobName] = useState("");
  const [jobDescription, setJobDescription] = useState("");
  const [creatingJob, setCreatingJob] = useState(false);
  const [statement, setStatement] = useState("");
  const [importance, setImportance] = useState(8.5);
  const [satisfaction, setSatisfaction] = useState(3.5);
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<{ error: StudioError; field: FailureField } | null>(null);

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
    setFailure(null);
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
    } catch (error) {
      setFailure({ error: asStudioError(error), field: "form" });
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
    setFailure(null);
    try {
      // The queue-aware path: it tries the sidecar and, when the network is
      // the only thing missing, saves the capture on this device instead of
      // dropping it. A real refusal still throws and lands on the field.
      await queueCapture({
        job_id: activeJobId,
        statement: statement.trim(),
        importance,
        satisfaction,
      });
      setStatement("");
    } catch (error) {
      const problem = asStudioError(error);
      // A fielded error lands beside the input it names; an out-of-range score
      // keeps today's behaviour and lands on the score fields; anything else
      // goes to form level.
      setFailure({ error: problem, field: fieldForError(problem) });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="stack">
      {queuedCaptures > 0 ? (
        <p className="queue-badge" role="status">
          {queuedCaptures === 1
            ? "1 capture waiting to sync."
            : `${queuedCaptures} captures waiting to sync.`}{" "}
          They arrive once when the sidecar is back.
        </p>
      ) : null}
      {failedCaptures.length > 0 ? (
        <p className="queue-badge queue-badge--failed" role="alert">
          {failedCaptures.length === 1
            ? "1 capture was refused by the sidecar and is kept on this device."
            : `${failedCaptures.length} captures were refused by the sidecar and are kept on this device.`}
        </p>
      ) : null}
      <form onSubmit={submit} className="form">
        <div className="field">
          <label htmlFor="dc-job">Job</label>
          <select
            id="dc-job"
            className="select"
            aria-describedby={jobs.length ? "dc-job-hint" : "dc-job-hint dc-job-first-hint"}
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
          <p className="field__hint" id="dc-job-hint">
            The job is what the customer is trying to get done. Every outcome measures how
            well they get it done.
          </p>
          {!jobs.length && (
            <p className="field__hint" id="dc-job-first-hint">
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
            aria-describedby={
              failure?.field === "statement"
                ? "dc-statement-hint dc-statement-error"
                : "dc-statement-hint"
            }
            value={statement}
            onChange={(event) => setStatement(event.target.value)}
          />
          <p className="field__hint" id="dc-statement-hint">
            What the customer measures success by: a direction, a unit of measure, the object
            it acts on, and the context. For example: “Minimize the time it takes to …”
          </p>
          {failure?.field === "statement" ? (
            <FailurePanel id="dc-statement-error" error={failure.error} />
          ) : null}
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
            aria-describedby="dc-importance-hint"
            onChange={(event) => setImportance(Number(event.target.value))}
          />
          <p className="field__hint" id="dc-importance-hint">
            How much this outcome matters, from 1 (not at all) to 10 (extremely), in steps of
            0.1.
          </p>
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
            aria-describedby={
              failure?.field === "range" ? "dc-satisfaction-hint dc-range-error" : "dc-satisfaction-hint"
            }
            onChange={(event) => setSatisfaction(Number(event.target.value))}
          />
          <p className="field__hint" id="dc-satisfaction-hint">
            How well it is met today, from 1 (not at all) to 10 (completely), in steps of 0.1.
          </p>
          {failure?.field === "range" ? (
            <FailurePanel id="dc-range-error" error={failure.error} />
          ) : null}
        </div>

        <p className="score-preview" aria-describedby="dc-score-hint">
          Opportunity <b>{formatOpportunityScore(calcOpp)}</b>
          <span>{isUnderserved(calcOpp) ? "underserved" : "appropriately served"}</span>
        </p>
        <p className="field__hint" id="dc-score-hint">
          A preview calculated from the two numbers you chose above — not customer evidence,
          and not independently verified.
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
          {failure?.field === "form" ? <FailurePanel error={failure.error} /> : null}
        </form>
      </details>
    </div>
  );
}
