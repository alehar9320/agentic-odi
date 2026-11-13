/**
 * The calls a turn is waiting on, said plainly while it waits.
 *
 * A long tool call makes a running turn look like a freeze, and the transcript
 * is the wrong place to answer that: it is the record of what happened, written
 * in the agent's own order. This strip sits below the last message and carries
 * only the calls still running or still asking a question — the ones the client
 * can actually see. It is a summary, never a queue: an "up next" row would be a
 * guess, so nothing here is inferred.
 *
 * The row reuses the transcript's own anatomy (`.tool-trace`, its dot, and the
 * `toolLabel` table), so a call reads the same wherever it is shown. It is not
 * a live region: the transcript already announces the turn once, and a second
 * voice ticking every second would be noise.
 */

import { useEffect, useState } from "react";

import { pendingCalls, type PendingCall } from "../../assistant/pending";
import { toolLabel } from "../../assistant/parts";
import { useStudio } from "../../state/StudioContext";

/**
 * Seconds since the store recorded the call's start, or null when it recorded
 * none. The start is observed, never invented; this only turns that timestamp
 * into a count a reader can watch, and stops when there is nothing to count.
 */
function useElapsed(startedAt: number | null): number | null {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (startedAt === null) {
      return;
    }
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [startedAt]);

  return startedAt === null ? null : Math.max(0, Math.floor((now - startedAt) / 1000));
}

function PendingRow({ call }: { call: PendingCall }) {
  const seconds = useElapsed(call.startedAt);

  return (
    <li className="pending-calls__row">
      <span className="tool-trace" data-aui-quote-selectable="false">
        <span className="tool-trace__dot" aria-hidden="true" />
        {toolLabel(call.name)}
        <span className="pending-calls__state">
          {call.awaitingApproval ? "waiting for your answer" : "working"}
        </span>
        {seconds !== null ? (
          <span className="pending-calls__elapsed" aria-hidden="true">
            {seconds}s
          </span>
        ) : null}
      </span>
      {call.prompt ? <span className="pending-calls__prompt">{call.prompt}</span> : null}
    </li>
  );
}

export function PendingCalls() {
  // The calls in flight live on the turn being streamed: the last message, when
  // it is the assistant's. An earlier turn cannot still be running.
  const last = useStudio().messages.at(-1);
  const pending = pendingCalls(last?.role === "assistant" ? (last.parts ?? []) : []);

  if (pending.length === 0) {
    return null;
  }

  return (
    <div className="pending-calls">
      <p className="pending-calls__head">
        Working · {pending.length} {pending.length === 1 ? "call" : "calls"}
      </p>
      <ul className="pending-calls__list">
        {pending.map((call) => (
          <PendingRow key={call.id} call={call} />
        ))}
      </ul>
    </div>
  );
}
