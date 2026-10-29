import { useMemo, useState, type KeyboardEvent } from "react";

import { useStudio } from "../../state/StudioContext";
import type { Evidence } from "../../types";
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
  const { canvasState, openPanel } = useStudio();
  const evidence = useMemo(() => canvasState.data?.evidence ?? [], [canvasState.data]);
  const jobs = useMemo(() => canvasState.data?.jobs ?? [], [canvasState.data]);
  const [storedOrder, setStoredOrder] = useState<string[]>(readStoredOrder);
  const [draggingId, setDraggingId] = useState<string | null>(null);

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
              <figcaption>{label}</figcaption>
              <blockquote>{item.content || "No text captured."}</blockquote>
              <span className="evidence__meta">
                {linkedJob ? `Linked to ${linkedJob}` : "Not linked to a job"}
                {item.source_name ? ` · ${item.source_name}` : ""}
                {item.item_type ? ` · ${item.item_type}` : ""}
              </span>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
