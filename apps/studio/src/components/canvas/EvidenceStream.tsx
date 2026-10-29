import { useMemo, useState, type FormEvent, type KeyboardEvent } from "react";

import { asStudioError } from "../../api/studioApi";
import { useStudio } from "../../state/StudioContext";
import type { Evidence, StudioError } from "../../types";
import { FailurePanel } from "../FailurePanel";
import { SignalIcon } from "../icons";

const ORDER_KEY = "agentic-odi.evidence-order";

function readStoredOrder(): string[] {
  try {
    const parsed: unknown = JSON.parse(localStorage.getItem(ORDER_KEY) ?? "[]");
    return Array.isArray(parsed) ? parsed.filter((id): id is string => typeof id === "string") : [];
  } catch {
    return [];
  }
}

function writeStoredOrder(ids: string[]) {
  try {
    localStorage.setItem(ORDER_KEY, JSON.stringify(ids));
  } catch {
    // A blocked storage quota must not break the panel.
  }
}

export function EvidenceStream() {
  const { canvasState, openPanel, promoteEvidence } = useStudio();
  const evidence = useMemo(() => canvasState.data?.evidence ?? [], [canvasState.data]);
  const jobs = useMemo(() => canvasState.data?.jobs ?? [], [canvasState.data]);
  const [storedOrder, setStoredOrder] = useState<string[]>(readStoredOrder);
  const [draggingId, setDraggingId] = useState<string | null>(null);

  const [promotingId, setPromotingId] = useState<string | null>(null);
  const [jobId, setJobId] = useState("");
  const [statement, setStatement] = useState("");
  const [importance, setImportance] = useState(8.5);
  const [satisfaction, setSatisfaction] = useState(3.5);
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<StudioError | null>(null);

  const ordered = useMemo(() => {
    const byId = new Map(evidence.map((item) => [item.id, item]));
    const known = storedOrder.filter((id) => byId.has(id));
    const rest = evidence.filter((item) => !known.includes(item.id)).map((item) => item.id);
    return [...known, ...rest].map((id) => byId.get(id) as Evidence);
  }, [evidence, storedOrder]);

  const jobNames = useMemo(
    () => new Map(jobs.map((job) => [job.id, job.name || job.id])),
    [jobs],
  );

  const commit = (next: Evidence[]) => {
    const ids = next.map((item) => item.id);
    setStoredOrder(ids);
    writeStoredOrder(ids);
  };

  const move = (id: string, delta: number) => {
    const index = ordered.findIndex((item) => item.id === id);
    const target = index + delta;
    if (index < 0 || target < 0 || target >= ordered.length) {
      return;
    }
    const next = [...ordered];
    [next[index], next[target]] = [next[target], next[index]];
    commit(next);
  };

  const dropOn = (targetId: string) => {
    if (!draggingId || draggingId === targetId) {
      setDraggingId(null);
      return;
    }
    const from = ordered.findIndex((item) => item.id === draggingId);
    const to = ordered.findIndex((item) => item.id === targetId);
    setDraggingId(null);
    if (from < 0 || to < 0) {
      return;
    }
    const next = [...ordered];
    const [moved] = next.splice(from, 1);
    next.splice(to, 0, moved);
    commit(next);
  };

  const onKeyDown = (event: KeyboardEvent<HTMLLIElement>, id: string) => {
    if (event.key === "ArrowUp") {
      event.preventDefault();
      move(id, -1);
    } else if (event.key === "ArrowDown") {
      event.preventDefault();
      move(id, 1);
    }
  };

  const startPromotion = (item: Evidence) => {
    setPromotingId(item.id);
    setJobId(item.job_id ?? jobs[0]?.id ?? "");
    setStatement((item.content || item.name || "").trim());
    setImportance(8.5);
    setSatisfaction(3.5);
    setFailure(null);
  };

  const submitPromotion = async (event: FormEvent) => {
    event.preventDefault();
    if (!promotingId || !jobId || !statement.trim() || busy) {
      return;
    }
    setBusy(true);
    setFailure(null);
    try {
      await promoteEvidence(promotingId, {
        target: "outcome",
        job_id: jobId,
        statement: statement.trim(),
        importance,
        satisfaction,
      });
      setPromotingId(null);
      setStatement("");
    } catch (error) {
      setFailure(asStudioError(error));
    } finally {
      setBusy(false);
    }
  };

  if (ordered.length === 0) {
    return (
      <section className="stack" aria-label="Customer evidence">
        <div className="evidence-empty">
          <span className="evidence-empty__icon" aria-hidden="true">
            <SignalIcon size={22} />
          </span>
          <p className="evidence-empty__title">No evidence captured yet.</p>
          <p className="evidence-empty__body">
            Nothing has been ingested in this build. Connect a source and the quotes, calls, and
            signals it brings will land here, linked to the job and outcome they support.
          </p>
          <button
            type="button"
            className="button button--ghost"
            onClick={() => openPanel("settings")}
          >
            Connect a source in Settings
          </button>
        </div>
      </section>
    );
  }

  return (
    <section className="stack" aria-label="Customer evidence">
      <p className="notice">Drag a record to reorder it, or focus one and press ↑ / ↓.</p>

      <ol className="stack" style={{ listStyle: "none", padding: 0, margin: 0 }}>
        {ordered.map((item, index) => {
          const label = item.name || item.source_name || "Untitled evidence";
          const linkedJob = item.job_id ? jobNames.get(item.job_id) : null;
          return (
            <li
              key={item.id}
              className="evidence"
              draggable
              tabIndex={0}
              aria-label={`${label} (${index + 1} of ${ordered.length})`}
              aria-roledescription="sortable evidence record"
              onKeyDown={(event) => onKeyDown(event, item.id)}
              onDragStart={() => setDraggingId(item.id)}
              onDragOver={(event) => event.preventDefault()}
              onDrop={(event) => {
                event.preventDefault();
                dropOn(item.id);
              }}
              onDragEnd={() => setDraggingId(null)}
              data-dragging={draggingId === item.id ? "true" : undefined}
            >
              <figcaption>
                {label}
                {/* The record itself stays in the tool that owns it; this is the way back. */}
                {item.url && (
                  <>
                    {" "}
                    <a
                      href={item.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="quiet-action"
                    >
                      Open in {item.source_name || "source"} ↗
                    </a>
                  </>
                )}
              </figcaption>
              <blockquote>{item.content || "No text captured."}</blockquote>
              <span className="evidence__meta">
                {linkedJob ? `Linked to ${linkedJob}` : "Not linked to a job"}
                {item.source_name ? ` · ${item.source_name}` : ""}
                {item.item_type ? ` · ${item.item_type}` : ""}
              </span>

              {promotingId === item.id ? (
                <form
                  className="form"
                  aria-label={`Promote ${label} to an outcome`}
                  onSubmit={submitPromotion}
                >
                  <div className="field">
                    <label htmlFor="promote-job">Job</label>
                    <select
                      id="promote-job"
                      className="select"
                      value={jobId}
                      onChange={(event) => setJobId(event.target.value)}
                    >
                      {jobs.map((job) => (
                        <option key={job.id} value={job.id}>
                          {job.id}: {job.name ?? ""}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="field">
                    <label htmlFor="promote-statement">Desired outcome</label>
                    <input
                      id="promote-statement"
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
                    <label htmlFor="promote-importance">Importance · {importance.toFixed(1)}</label>
                    <input
                      id="promote-importance"
                      type="range"
                      min={1}
                      max={10}
                      step={0.1}
                      value={importance}
                      onChange={(event) => setImportance(Number(event.target.value))}
                    />
                  </div>

                  <div className="field">
                    <label htmlFor="promote-satisfaction">
                      Current satisfaction · {satisfaction.toFixed(1)}
                    </label>
                    <input
                      id="promote-satisfaction"
                      type="range"
                      min={1}
                      max={10}
                      step={0.1}
                      value={satisfaction}
                      onChange={(event) => setSatisfaction(Number(event.target.value))}
                    />
                  </div>

                  {failure ? <FailurePanel error={failure} /> : null}

                  <div>
                    <button
                      type="submit"
                      className="button"
                      disabled={busy || !statement.trim() || !jobId}
                    >
                      Save outcome
                    </button>
                    <button
                      type="button"
                      className="button button--ghost"
                      onClick={() => {
                        setPromotingId(null);
                        setFailure(null);
                      }}
                    >
                      Cancel
                    </button>
                  </div>
                </form>
              ) : (
                <button
                  type="button"
                  className="button button--ghost"
                  aria-label={`Turn ${label} into an outcome`}
                  disabled={!jobs.length}
                  onClick={() => startPromotion(item)}
                >
                  Turn into outcome
                </button>
              )}
            </li>
          );
        })}
      </ol>
    </section>
  );
}
