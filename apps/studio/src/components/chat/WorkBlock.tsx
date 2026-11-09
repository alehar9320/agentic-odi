/**
 * One run row: the thinking and the calls a turn did, folded into a line.
 *
 * The transcript is an audit trail, so nothing here hides a call — a settled
 * turn keeps its reasoning and every tool trace, one click away. What changes is
 * the default view: the answer is what a reader came for, and the work behind it
 * is a record they open rather than a wall of chips they scroll past.
 *
 * Which parts belong to a run is `workGrouping`'s decision, in its own module —
 * it is pure over the runtime's parts and needs no React to be tested.
 */

import { useEffect, useId, useRef, useState, type ReactNode } from "react";

import { ChevronDownIcon } from "../icons";

function countOf(calls: number, noun: string): string {
  return `${calls} ${noun}${calls === 1 ? "" : "s"}`;
}

/**
 * The disclosure itself: one line, and the work underneath it.
 *
 * It opens while the turn runs, so a reader can watch the work happen, and
 * closes on the transition to settled — the moment the work becomes a record.
 * After that only the reader opens it again. A turn restored from history never
 * ran in front of anyone, so it says how many calls it holds and not how long
 * they took: the timings were never recorded here.
 */
export function WorkBlock({
  calls,
  running,
  children,
}: {
  calls: number;
  running: boolean;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(running);
  const [seconds, setSeconds] = useState<number | null>(null);
  const startedAt = useRef<number | null>(null);
  const panelId = useId();

  useEffect(() => {
    if (running) {
      if (startedAt.current === null) {
        startedAt.current = Date.now();
      }
      return;
    }
    const started = startedAt.current;
    if (started === null) {
      return;
    }
    startedAt.current = null;
    setOpen(false);
    // One tick after the run settles, so the duration lands as a settled value
    // rather than writing state during the effect that observed the change.
    const timer = window.setTimeout(() => {
      setSeconds(Math.max(1, Math.round((Date.now() - started) / 1000)));
    }, 0);
    return () => window.clearTimeout(timer);
  }, [running]);

  const tally = countOf(calls, "call");
  const label = running
    ? calls > 0
      ? `Working… · ${tally}`
      : "Working…"
    : seconds === null
      ? `Worked · ${tally}`
      : `Worked for ${seconds}s · ${tally}`;

  return (
    <div className={`work-block${running ? " is-running" : ""}`}>
      <button
        type="button"
        className="work-block__trigger"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((value) => !value)}
      >
        <span>{label}</span>
        <ChevronDownIcon className={`work-block__chevron${open ? " is-open" : ""}`} size={12} />
      </button>
      <div className="work-block__body" id={panelId} hidden={!open}>
        {children}
      </div>
    </div>
  );
}
