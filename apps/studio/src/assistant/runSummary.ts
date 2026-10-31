/**
 * One line per assistant turn: what it did, how long it took, what went wrong.
 *
 * Pure and clock-free. The timing it reports comes from the parts it is handed,
 * so a turn whose runtime tracks nothing shows no duration rather than a
 * duration invented here.
 */

/** The part fields a run row reads; assistant-ui's tool-call parts satisfy it. */
export type RunCall = {
  readonly toolName: string;
  readonly result?: unknown;
  readonly isError?: boolean;
  readonly timing?: { startedAt: number; completedAt?: number };
};

export type RunSummary = {
  calls: number;
  /** Calls that were asked to change the Studio's data and were not refused. */
  writes: number;
  /** Tool names that errored, in stream order. */
  failures: string[];
  /** Tool names the user refused, in stream order. */
  declined: string[];
  startedAt?: number;
  finishedAt?: number;
  durationMs?: number;
};

/**
 * The first word of a Studio tool name that mutates. Reads (`list_*`, `get_*`,
 * `search_*`) are absent by design; they are the majority and a row that
 * counted them as writes would overstate what touched the user's data.
 */
const WRITE_VERBS = new Set([
  "add",
  "append",
  "archive",
  "cancel",
  "claim",
  "create",
  "delete",
  "dismiss",
  "mark",
  "promote",
  "record",
  "remove",
  "save",
  "schedule",
  "set",
  "start",
  "stop",
  "update",
  "write",
]);

function statusOf(call: RunCall): string | undefined {
  const { result } = call;
  if (result === null || typeof result !== "object") {
    return undefined;
  }
  const status = (result as { status?: unknown }).status;
  return typeof status === "string" ? status : undefined;
}

function isFailure(call: RunCall): boolean {
  return call.isError === true || statusOf(call) === "error";
}

function isDeclined(call: RunCall): boolean {
  return statusOf(call) === "declined";
}

function isWrite(call: RunCall): boolean {
  return WRITE_VERBS.has(call.toolName.split("_")[0]);
}

function duration(startedAt: number, finishedAt: number): number | undefined {
  const ms = finishedAt - startedAt;
  return ms >= 0 ? ms : undefined;
}

export function summarizeRun(calls: readonly RunCall[]): RunSummary {
  const summary: RunSummary = {
    calls: calls.length,
    writes: 0,
    failures: [],
    declined: [],
  };
  const starts: number[] = [];
  const finishes: number[] = [];
  let open = false;

  for (const call of calls) {
    if (isFailure(call)) {
      summary.failures.push(call.toolName);
    } else if (isDeclined(call)) {
      summary.declined.push(call.toolName);
    } else if (call.result !== undefined) {
      if (isWrite(call)) {
        summary.writes += 1;
      }
    }
    if (call.timing) {
      starts.push(call.timing.startedAt);
      if (call.timing.completedAt === undefined) {
        open = true;
      } else {
        finishes.push(call.timing.completedAt);
      }
    }
  }

  if (starts.length > 0) {
    summary.startedAt = Math.min(...starts);
    if (!open) {
      summary.finishedAt = Math.max(...finishes);
      summary.durationMs = duration(summary.startedAt, summary.finishedAt);
    }
  }
  return summary;
}

function label(toolName: string): string {
  return toolName.replace(/_/g, " ");
}

function count(noun: string, n: number): string {
  return `${n} ${noun}${n === 1 ? "" : "s"}`;
}

function named(prefix: string, names: readonly string[]): string {
  return `${prefix}: ${names.map(label).join(", ")}`;
}

export function formatRunSummary(summary: RunSummary): string {
  const segments = [count("call", summary.calls)];
  if (summary.durationMs !== undefined) {
    segments.push(`${(summary.durationMs / 1000).toFixed(1)}s`);
  }
  if (summary.writes > 0) {
    segments.push(count("write", summary.writes));
  }
  if (summary.failures.length > 0) {
    segments.push(named(count("error", summary.failures.length), summary.failures));
  }
  if (summary.declined.length > 0) {
    segments.push(named(`${summary.declined.length} declined`, summary.declined));
  }
  return segments.join(" · ");
}
