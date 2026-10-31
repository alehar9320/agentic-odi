import { describe, expect, it } from "vitest";

import { formatRunSummary, summarizeRun, type RunCall } from "./runSummary";

function ok(toolName: string): RunCall {
  return { toolName, result: { status: "ok", preview: "" } };
}

function failed(toolName: string): RunCall {
  return { toolName, result: { status: "error", preview: "" }, isError: true };
}

function declined(toolName: string): RunCall {
  return { toolName, result: { status: "declined", preview: "" } };
}

/** A call the stream has not settled: no result yet. */
function running(toolName: string): RunCall {
  return { toolName };
}

describe("summarizeRun", () => {
  it("reports an empty turn without inventing a duration", () => {
    expect(summarizeRun([])).toEqual({
      calls: 0,
      writes: 0,
      failures: [],
      declined: [],
      startedAt: undefined,
      finishedAt: undefined,
      durationMs: undefined,
    });
  });

  it("counts one successful read", () => {
    const summary = summarizeRun([ok("list_jobs")]);
    expect(summary).toMatchObject({ calls: 1, writes: 0, failures: [], declined: [] });
  });

  it("counts a mutating call as a write", () => {
    expect(
      summarizeRun([
        ok("add_job"),
        ok("update_outcome"),
        ok("delete_step"),
        ok("mark_signal_read"),
        ok("dismiss_signal"),
        ok("cancel_scheduled_work"),
        ok("promote_evidence"),
        ok("list_jobs"),
        ok("get_evidence"),
        ok("search_signals"),
      ]),
    ).toMatchObject({ calls: 10, writes: 7 });
  });

  it("counts a call that changed something as a write", () => {
    expect(
      summarizeRun([
        ok("add_job"),
        failed("delete_job"),
        declined("dismiss_signal"),
        ok("list_jobs"),
      ]),
    ).toMatchObject({ calls: 4, writes: 1, failures: ["delete_job"], declined: ["dismiss_signal"] });
  });

  it("names failures and declines in the order they happened", () => {
    expect(summarizeRun([ok("add_job"), failed("delete_job"), declined("dismiss_signal")])).toEqual({
      calls: 3,
      writes: 1,
      failures: ["delete_job"],
      declined: ["dismiss_signal"],
      startedAt: undefined,
      finishedAt: undefined,
      durationMs: undefined,
    });
  });

  it("adds up the wall clock when every call finished", () => {
    expect(
      summarizeRun([
        { ...ok("list_jobs"), timing: { startedAt: 1_000, completedAt: 2_500 } },
        { ...ok("add_job"), timing: { startedAt: 2_500, completedAt: 5_400 } },
      ]),
    ).toMatchObject({ startedAt: 1_000, finishedAt: 5_400, durationMs: 4_400 });
  });

  it("withholds the duration while a call is still open", () => {
    const summary = summarizeRun([
      { ...ok("list_jobs"), timing: { startedAt: 1_000, completedAt: 2_500 } },
      { ...running("add_job"), timing: { startedAt: 2_500 } },
    ]);
    expect(summary.startedAt).toBe(1_000);
    expect(summary.finishedAt).toBeUndefined();
    expect(summary.durationMs).toBeUndefined();
  });

  it("degrades to no duration when no call carries timing", () => {
    const summary = summarizeRun([ok("list_jobs"), ok("add_job")]);
    expect(summary.startedAt).toBeUndefined();
    expect(summary.finishedAt).toBeUndefined();
    expect(summary.durationMs).toBeUndefined();
  });
});

describe("formatRunSummary", () => {
  it("writes the counts, duration, and writes for a settled turn", () => {
    const timed = (toolName: string): RunCall => ({
      ...ok(toolName),
      timing: { startedAt: 0, completedAt: 12_400 },
    });
    const calls = [
      timed("add_job"),
      timed("add_outcome"),
      ...Array.from({ length: 7 }, () => timed("list_jobs")),
    ];
    expect(formatRunSummary(summarizeRun(calls))).toBe("9 calls · 12.4s · 2 writes");
  });

  it("says one call", () => {
    expect(formatRunSummary(summarizeRun([ok("list_jobs")]))).toBe("1 call");
  });

  it("drops the writes segment when the turn only read", () => {
    expect(formatRunSummary(summarizeRun([ok("list_jobs"), ok("get_evidence")]))).toBe("2 calls");
  });

  it("keeps the sentence whole without a duration", () => {
    expect(formatRunSummary(summarizeRun([ok("list_jobs"), ok("add_job")]))).toBe("2 calls · 1 write");
  });

  it("names the calls that did not land", () => {
    expect(
      formatRunSummary(summarizeRun([ok("add_job"), failed("delete_job"), declined("dismiss_signal")])),
    ).toBe("3 calls · 1 write · 1 error: delete job · 1 declined: dismiss signal");
  });

  it("lists several failures together", () => {
    expect(formatRunSummary(summarizeRun([failed("delete_job"), failed("add_evidence")]))).toBe(
      "2 calls · 2 errors: delete job, add evidence",
    );
  });

  it("never prints NaN", () => {
    for (const calls of [[], [ok("list_jobs")], [running("list_jobs")]]) {
      expect(formatRunSummary(summarizeRun(calls))).not.toContain("NaN");
    }
  });
});
