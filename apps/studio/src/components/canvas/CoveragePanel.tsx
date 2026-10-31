import { useEffect, useState } from "react";

import { useStudio } from "../../state/StudioContext";
import { FailurePanel } from "../FailurePanel";

/** A stage row's numbers, or an em dash when the report has not arrived. */
function count(value: number | undefined): string {
  return value === undefined ? "—" : String(value);
}

/**
 * Coverage: what the research covers, and what it does not.
 *
 * The panel reads `get_coverage`, which reports every stage in canonical order
 * — including the empty ones. A gap is a stage with no outcomes, named in the
 * "not yet covered" list; it is never an omitted row, so "nothing here" is a
 * finding the reader can see rather than infer.
 */
export function CoveragePanel() {
  const { canvasState, coverageState, refreshCoverage, stagesState } = useStudio();
  const jobs = canvasState.data?.jobs ?? [];
  const [jobId, setJobId] = useState<string>("");

  const activeJobId = jobId || jobs[0]?.id || "";

  useEffect(() => {
    if (activeJobId) {
      void refreshCoverage(activeJobId);
    }
  }, [activeJobId, refreshCoverage]);

  const stageName = (id: string) =>
    (stagesState.data ?? []).find((stage) => stage.id === id)?.name ?? id;

  if (coverageState.kind === "error") {
    return (
      <section className="fade-in">
        <p className="section-title">Coverage</p>
        <FailurePanel
          error={coverageState.error}
          onRetry={() => void refreshCoverage(activeJobId)}
          retryText="reload"
        />
      </section>
    );
  }

  const report = coverageState.data;

  return (
    <section className="fade-in">
      <p className="section-title">Coverage</p>
      <p className="caption">
        What the research covers across the eight stages of the job, and what it does not.
      </p>

      {jobs.length > 1 && (
        <div className="field">
          <label htmlFor="cov-job">Job</label>
          <select
            id="cov-job"
            className="select"
            value={activeJobId}
            onChange={(event) => setJobId(event.target.value)}
          >
            {jobs.map((job) => (
              <option key={job.id} value={job.id}>
                {job.id}: {job.name ?? "Untitled job"}
              </option>
            ))}
          </select>
        </div>
      )}

      {!activeJobId ? (
        <p className="toast toast--info" role="status">
          No job to measure yet. Capture a job and its outcomes first.
        </p>
      ) : coverageState.kind === "loading" && !report ? (
        <p className="caption">Measuring coverage…</p>
      ) : (
        <>
          <table className="cov-table">
            <caption className="caption">Outcomes, measured scores, and quotes per stage</caption>
            <thead>
              <tr>
                <th scope="col">Stage</th>
                <th scope="col">Outcomes</th>
                <th scope="col">Measured</th>
                <th scope="col">Quotes</th>
              </tr>
            </thead>
            <tbody>
              {(report?.per_stage ?? []).map((row) => (
                <tr key={row.stage} data-covered={row.outcomes > 0 ? "yes" : "no"}>
                  <th scope="row">{stageName(row.stage)}</th>
                  <td>{count(row.outcomes)}</td>
                  <td>{count(row.measured)}</td>
                  <td>{count(row.quotes)}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <p className="cov-totals" role="status">
            Outcomes {count(report?.totals.outcomes)} · measured {count(report?.totals.measured)} ·
            quotes {count(report?.totals.quotes)}
          </p>
          <p className="cov-unassigned">
            Unassigned: {count(report?.totals.unassigned_outcomes)} outcomes,{" "}
            {count(report?.totals.unassigned_quotes)} quotes
          </p>
          <p className="cov-gaps">
            Not yet covered:{" "}
            {report && report.gaps.length > 0
              ? report.gaps.map(stageName).join(", ")
              : "every stage has at least one outcome"}
          </p>
        </>
      )}
    </section>
  );
}
