/**
 * "Still working" while the run is silent.
 *
 * A tool call can think for tens of seconds; before this, the transcript looked
 * identical to a hang once the first sentence had landed. The signal comes from
 * assistant-ui's stall detection, which watches text, reasoning, tool arguments,
 * and tool-result availability — never from a timer of ours watching the DOM.
 *
 * `unstable_useMessageStallDetection` is experimental (verified against
 * `@assistant-ui/react@0.15.31`); it is called here, in one component, so an
 * upgrade is one file.
 */

import { unstable_useMessageStallDetection, useAuiState } from "@assistant-ui/react";

/**
 * Eight seconds. A local MCP call usually returns well inside this; a model
 * provider's first token can take longer, and a tool that legitimately runs for
 * half a minute should read as work rather than a freeze. The default of 2s is
 * too eager to be honest.
 */
export const STALL_THRESHOLD_MS = 8_000;

export function StallNotice() {
  const running = useAuiState((state) => state.message.status?.type === "running");
  const { stalled, stalledForMs } = unstable_useMessageStallDetection({
    thresholdMs: STALL_THRESHOLD_MS,
  });

  if (!running || !stalled) {
    return null;
  }

  const seconds = Math.max(1, Math.round(stalledForMs / 1000));

  return (
    <div className="stall">
      {/* The seconds tick, so they are decoration for sighted readers only. */}
      <p className="stall__line" aria-hidden="true">
        Still working · no new output for {seconds}s
      </p>
      {/* One stable sentence: announced when the stall begins, not every second. */}
      <p className="sr-only" role="status">
        Still working — no new output yet.
      </p>
    </div>
  );
}
