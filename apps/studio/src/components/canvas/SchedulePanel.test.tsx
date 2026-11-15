import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { formatClockTime } from "../../lib/relativeTime";
import { SchedulePanel } from "./SchedulePanel";

const api = vi.hoisted(() => ({
  scheduleWork: vi.fn<(payload: Record<string, unknown>) => Promise<unknown>>(),
  triggerScheduledWork: vi.fn<(id: string, mcpUrl: string) => Promise<unknown>>(),
  cancelScheduledWork: vi.fn<(id: string, mcpUrl: string) => Promise<unknown>>(),
}));

vi.mock("../../api/studioApi", () => ({
  scheduleWork: api.scheduleWork,
  triggerScheduledWork: api.triggerScheduledWork,
  cancelScheduledWork: api.cancelScheduledWork,
}));

const harness = vi.hoisted(() => ({
  state: {
    canvas: {
      jobs: [{ id: "JOB-1", name: "Ship a service" }],
      steps: [],
      outcomes: [],
      scheduled_work: [],
    } as unknown,
    settings: { mcp_url: "http://mcp" },
    pushToast: vi.fn(),
    refreshCanvas: vi.fn(async () => {}),
  },
}));

vi.mock("../../state/StudioContext", () => ({
  useStudio: () => harness.state,
}));

const task = {
  id: "work-1",
  name: "Nightly audit",
  schedule_expression: "+1h",
  agent_id: "default-agent",
  trigger_type: "oneshot" as const,
  status: "running" as const,
  result_summary: "Dispatched at 2026-10-26T09:00:00Z; no executor is installed, so nothing has run.",
};

const failedTask = {
  id: "work-2",
  name: "Morning brief",
  schedule_expression: "0 2 * * *",
  agent_id: "default-agent",
  trigger_type: "cron" as const,
  status: "scheduled" as const,
  last_run_at: "2026-05-01T02:00:00+00:00",
  next_run_at: "2026-05-01T02:04:00+00:00",
  last_status: "failed" as const,
  attempts: 2,
  last_error: "RuntimeError: model unreachable",
};

const okTask = {
  id: "work-3",
  name: "Weekly sweep",
  schedule_expression: "0 2 * * *",
  agent_id: "default-agent",
  trigger_type: "cron" as const,
  status: "completed" as const,
  last_run_at: "2026-05-01T02:00:00+00:00",
  next_run_at: null,
  last_status: "ok" as const,
  attempts: 0,
  last_error: null,
};

beforeEach(() => {
  api.scheduleWork.mockReset();
  api.triggerScheduledWork.mockReset();
  api.cancelScheduledWork.mockReset();
  harness.state.pushToast.mockReset();
  harness.state.canvas = {
    jobs: [{ id: "JOB-1", name: "Ship a service" }],
    steps: [],
    outcomes: [],
    scheduled_work: [],
  } as unknown;
});

describe("SchedulePanel", () => {
  it("says plainly that nothing reads the schedule expression yet", () => {
    render(<SchedulePanel />);

    expect(screen.getByLabelText(/when/i)).toBeInTheDocument();
    expect(screen.getByText(/stored verbatim, not parsed yet/i)).toBeInTheDocument();
    expect(screen.getByText(/Nothing reads this expression yet/i)).toBeInTheDocument();
  });

  it("schedules with the agent id it was given, not a name baked in here", async () => {
    api.scheduleWork.mockResolvedValue({ ok: true });
    render(<SchedulePanel agentId="ops-agent" />);

    fireEvent.change(screen.getByLabelText(/what should the agent do/i), {
      target: { value: "Nightly audit" },
    });
    fireEvent.change(screen.getByLabelText(/when/i), { target: { value: "+1h" } });
    fireEvent.change(screen.getByLabelText(/^job/i), { target: { value: "JOB-1" } });
    fireEvent.click(screen.getByRole("button", { name: /schedule work/i }));

    await waitFor(() => {
      expect(api.scheduleWork).toHaveBeenCalledWith(
        expect.objectContaining({
          name: "Nightly audit",
          schedule_expression: "+1h",
          agent_id: "ops-agent",
          job_id: "JOB-1",
          mcp_url: "http://mcp",
        }),
      );
    });
    expect(harness.state.refreshCanvas).toHaveBeenCalled();
  });

  it("falls back to the backend's default agent when none is given", async () => {
    api.scheduleWork.mockResolvedValue({ ok: true });
    render(<SchedulePanel />);

    fireEvent.change(screen.getByLabelText(/what should the agent do/i), {
      target: { value: "Weekly sweep" },
    });
    fireEvent.click(screen.getByRole("button", { name: /schedule work/i }));

    await waitFor(() => {
      expect(api.scheduleWork).toHaveBeenCalledWith(
        expect.objectContaining({ agent_id: "default-agent" }),
      );
    });
  });

  it("shows a dispatched task with the note that nothing ran", () => {
    harness.state.canvas = {
      jobs: [],
      steps: [],
      outcomes: [],
      scheduled_work: [task],
    } as unknown;

    render(<SchedulePanel />);

    expect(screen.getByText("Nightly audit")).toBeInTheDocument();
    expect(screen.getByText(/no executor is installed, so nothing has run/i)).toBeInTheDocument();
    expect(screen.getByText("running")).toBeInTheDocument();
  });

  it("dispatches and cancels a task", async () => {
    api.triggerScheduledWork.mockResolvedValue({ ok: true });
    api.cancelScheduledWork.mockResolvedValue({ ok: true });
    harness.state.canvas = {
      jobs: [],
      steps: [],
      outcomes: [],
      scheduled_work: [task],
    } as unknown;

    render(<SchedulePanel />);

    fireEvent.click(screen.getByRole("button", { name: /dispatch/i }));
    await waitFor(() => {
      expect(api.triggerScheduledWork).toHaveBeenCalledWith("work-1", "http://mcp");
    });

    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));
    await waitFor(() => {
      expect(api.cancelScheduledWork).toHaveBeenCalledWith("work-1", "http://mcp");
    });
  });

  it("shows a failed run with its reason, attempt count, and next retry", () => {
    harness.state.canvas = {
      jobs: [],
      steps: [],
      outcomes: [],
      scheduled_work: [failedTask],
    } as unknown;

    render(<SchedulePanel />);

    // The retry time is formatted from the record, never computed here.
    const retryAt = formatClockTime(failedTask.next_run_at);
    expect(
      screen.getByText(
        new RegExp(
          `Failed — RuntimeError: model unreachable · attempt 2 of 3 · retrying at ${retryAt}`,
        ),
      ),
    ).toBeInTheDocument();
  });

  it("shows a healthy run as ran, with no error", () => {
    harness.state.canvas = {
      jobs: [],
      steps: [],
      outcomes: [],
      scheduled_work: [okTask],
    } as unknown;

    render(<SchedulePanel />);

    expect(screen.getByText(/Ran at/)).toBeInTheDocument();
    expect(screen.queryByText(/Failed/)).not.toBeInTheDocument();
  });

  it("renders no run line for an item that has not run", () => {
    harness.state.canvas = {
      jobs: [],
      steps: [],
      outcomes: [],
      scheduled_work: [task],
    } as unknown;

    render(<SchedulePanel />);

    expect(screen.queryByText(/Failed/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Ran at/)).not.toBeInTheDocument();
  });
});
