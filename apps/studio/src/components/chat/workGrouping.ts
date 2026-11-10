/**
 * Which parts of a reply are one run of work.
 *
 * Written against the installed `@assistant-ui/react@0.15.31`, and its source
 * rather than its docs: `ChainOfThoughtPrimitive.Parts` groups through
 * `groupMessageParts`, which starts a run at any adjacent `tool-call` or
 * `reasoning` part. A pending write approval is a `tool-call` part, so the
 * chain-of-thought primitive would fold a question away with the history.
 * `groupPartByType` has the same flaw — it keys by part type or tool name
 * alone. So this groups by hand and ends a run at an unanswered approval,
 * leaving it in the message body where it can be answered.
 */

import type { PartState } from "@assistant-ui/react";

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
