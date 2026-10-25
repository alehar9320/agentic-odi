import { describe, expect, it } from "vitest";

import {
  activityLabel,
  applyToolEvent,
  formatDuration,
  runSummary,
  runningStep,
  stepLabel,
  type RunStep,
} from "./run";

function started(name: string, at = 0): RunStep[] {
  return applyToolEvent([], { name, status: "start" }, at);
}

describe("applyToolEvent", () => {
  it("keeps one step per call instead of one per event", () => {
    let steps = started("get_jobs", 0);
    steps = applyToolEvent(steps, { name: "get_jobs", status: "ok" }, 300);

    expect(steps).toHaveLength(1);
    expect(steps[0]).toMatchObject({ name: "get_jobs", status: "ok", startedAt: 0, endedAt: 300 });
  });

  it("records an error with the tool's own words", () => {
    let steps = started("get_jobs", 10);
    steps = applyToolEvent(
      steps,
      { name: "get_jobs", status: "error", preview: "MCP server unreachable" },
      60,
    );

    expect(steps[0].status).toBe("error");
    expect(steps[0].preview).toBe("MCP server unreachable");
  });

  it("keeps repeated calls to the same tool as separate steps", () => {
    let steps = started("get_outcomes", 0);
    steps = applyToolEvent(steps, { name: "get_outcomes", status: "ok" }, 100);
    steps = applyToolEvent(steps, { name: "get_outcomes", status: "start" }, 120);
    steps = applyToolEvent(steps, { name: "get_outcomes", status: "ok" }, 200);

    expect(steps.map((step) => step.status)).toEqual(["ok", "ok"]);
    expect(steps[0].id).not.toBe(steps[1].id);
  });

  it("resolves only the newest open call, so parallel calls stay distinct", () => {
    let steps = started("get_jobs", 0);
    steps = applyToolEvent(steps, { name: "get_evidence", status: "start" }, 10);
    steps = applyToolEvent(steps, { name: "get_evidence", status: "ok" }, 20);

    expect(steps[0].status).toBe("running");
    expect(steps[1].status).toBe("ok");
  });

  it("records a result whose start it never saw rather than dropping it", () => {
    const steps = applyToolEvent([], { name: "render_ui", status: "ok" }, 50);

    expect(steps).toEqual([
      expect.objectContaining({ name: "render_ui", status: "ok", startedAt: 50, endedAt: 50 }),
    ]);
  });

  it("never renders an unnamed step", () => {
    const steps = applyToolEvent([], { name: "  ", status: "start" }, 0);

    expect(steps[0].name).toBe("tool");
  });
});

describe("stepLabel", () => {
  it("speaks the studio's own tools in plain words", () => {
    expect(stepLabel("get_jobs")).toBe("Reading your jobs");
    expect(stepLabel("render_ui")).toBe("Drawing a card");
  });

  it("falls back to the raw tool name for anything the MCP server adds", () => {
    expect(stepLabel("search_tickets")).toBe("search tickets");
    expect(stepLabel("")).toBe("Using a tool");
  });
});

describe("activityLabel", () => {
  it("names the tool in flight over the phase", () => {
    const steps = started("get_job_map", 0);

    expect(activityLabel("model", steps)).toBe("Reading the job map");
  });

  it("falls back to the sidecar phase, then to thinking", () => {
    expect(activityLabel("health_check", [])).toBe("Waking the model");
    expect(activityLabel("mcp_tools", [])).toBe("Opening your studio tools");
    expect(activityLabel(null, [])).toBe("Thinking");
  });

  it("ignores a phase it has never heard of", () => {
    expect(activityLabel("warp_drive", [])).toBe("Thinking");
  });
});

describe("runSummary", () => {
  it("counts the calls and the time they took", () => {
    let steps = started("get_jobs", 0);
    steps = applyToolEvent(steps, { name: "get_jobs", status: "ok" }, 1000);
    steps = applyToolEvent(steps, { name: "get_outcomes", status: "start" }, 1000);
    steps = applyToolEvent(steps, { name: "get_outcomes", status: "ok" }, 2400);

    expect(runSummary(steps, 2400)).toBe("2 tools · 2.4s");
  });

  it("says when a tool failed", () => {
    let steps = started("get_jobs", 0);
    steps = applyToolEvent(steps, { name: "get_jobs", status: "error" }, 500);

    expect(runSummary(steps, 500)).toBe("1 tool · 1 failed · 0.5s");
  });

  it("uses the current time for a step that has not finished", () => {
    expect(runSummary(started("get_jobs", 100), 1600)).toBe("1 tool · 1.5s");
  });

  it("says nothing about a run that used no tools", () => {
    expect(runSummary([], 0)).toBe("");
  });
});

describe("runningStep", () => {
  it("finds the step still in flight, if any", () => {
    let steps = started("get_jobs", 0);
    steps = applyToolEvent(steps, { name: "get_jobs", status: "ok" }, 10);
    expect(runningStep(steps)).toBeNull();

    steps = applyToolEvent(steps, { name: "get_evidence", status: "start" }, 20);
    expect(runningStep(steps)?.name).toBe("get_evidence");
  });
});

describe("formatDuration", () => {
  it("stays to one short form", () => {
    expect(formatDuration(0)).toBe("0.0s");
    expect(formatDuration(420)).toBe("0.4s");
    expect(formatDuration(12_400)).toBe("12s");
    expect(formatDuration(125_000)).toBe("2m 5s");
  });

  it("never prints nonsense for a broken clock", () => {
    expect(formatDuration(-1)).toBe("0s");
    expect(formatDuration(Number.NaN)).toBe("0s");
  });
});
