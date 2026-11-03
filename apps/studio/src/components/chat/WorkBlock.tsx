/**
 * One run row: the thinking and the calls a turn did, folded into a line.
 *
 * The transcript is an audit trail, so nothing here hides a call — a settled
 * turn keeps its reasoning and every tool trace, one click away. What changes is
 * the default view: the answer is what a reader came for, and the work behind it
 * is a record they open rather than a wall of chips they scroll past.
 *
 * `MessagePrimitive.GroupedParts` rather than `ChainOfThoughtPrimitive.Parts`,
 * checked against the installed `@assistant-ui/react@0.15.31`: the chain-of-
 * thought primitive groups strictly by part type — `groupMessageParts` starts a
 * run at any adjacent `tool-call` or `reasoning` part — so a pending write
 * approval, which is a `tool-call` part, would be gathered into the collapsed
 * group. A question is not history: `workGrouping` below ends a run at an
 * unanswered approval and leaves it in the message body, answerable.
 */

import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import type { PartState } from "@assistant-ui/react";

import { ChevronDownIcon } from "../icons";

/** The group key `GroupedParts` hands back for a run of work. */
const WORK_GROUP = "group-work";

/**
 * A tool call that is still asking something, rather than reporting an answer.
 * The same test `ToolPart` uses to decide whether to render the gate.
 */
function isQuestion(part: PartState): boolean {
  if (part.type !== "tool-call") {
    return false;
  }
  const approval = part.approval;
  return approval !== undefined && approval.approved === undefined && part.result === undefined;
}

function isWork(part: PartState): boolean {
  return part.type === "reasoning" || (part.type === "tool-call" && !isQuestion(part));
}

/**
 * The `groupBy` for one message: consecutive thinking and answered calls become
 * a single run, everything else — prose, cards, and an open approval — stays
 * exactly where it is.
 *
 * A run with no call in it is left alone. Thinking on its own already owns a
 * disclosure that says how long the model thought for; wrapping it in a second
 * one would be a door inside a door.
 */
export function workGrouping(
  parts: readonly PartState[],
): (part: PartState) => readonly [typeof WORK_GROUP] | null {
  const grouped = new Map<PartState, readonly [typeof WORK_GROUP]>();
  let run: PartState[] = [];

  const closeRun = () => {
    if (run.some((part) => part.type === "tool-call")) {
      for (const part of run) {
        grouped.set(part, [WORK_GROUP]);
      }
    }
    run = [];
  };

  for (const part of parts) {
    if (isWork(part)) {
      run.push(part);
    } else {
      closeRun();
    }
  }
  closeRun();

  return (part) => grouped.get(part) ?? null;
}

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
