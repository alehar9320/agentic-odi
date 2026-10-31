import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

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
  status: "scheduled" as const,
  next_run_at: "2026-10-29T13:00:00+00:00",
  last_run_at: null,
  trigger_requested_at: null,
  result_summary: null,
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
  it("explains that the expression is parsed when scheduled", () => {
    render(<SchedulePanel />);

    expect(screen.getByLabelText(/when/i)).toBeInTheDocument();
    expect(screen.getByText(/parsed when you schedule it/i)).toBeInTheDocument();
    expect(
      screen.getByText(/decides whether the work runs once or repeatedly/i),
    ).toBeInTheDocument();
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
    expect(api.scheduleWork.mock.calls[0][0]).not.toHaveProperty("trigger_type");
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

  it("shows the real next run and last run for a scheduled task", () => {
    harness.state.canvas = {
      jobs: [],
      steps: [],
      outcomes: [],
      scheduled_work: [{ ...task, last_run_at: "2026-10-28T13:00:00+00:00" }],
    } as unknown;

    render(<SchedulePanel />);

    expect(screen.getByText("Nightly audit")).toBeInTheDocument();
    expect(screen.getByText(/next run/i)).toBeInTheDocument();
    expect(screen.getByText(/last run/i)).toBeInTheDocument();
    expect(screen.getByText("scheduled")).toBeInTheDocument();
  });

  it("shows a queued occurrence as queued, not as a result", () => {
    harness.state.canvas = {
      jobs: [],
      steps: [],
      outcomes: [],
      scheduled_work: [
        {
          ...task,
          trigger_requested_at: "2026-10-29T12:00:00+00:00",
          result_summary: "Queued for the orchestrator; not run yet.",
        },
      ],
    } as unknown;

    render(<SchedulePanel />);

    expect(screen.getAllByText(/queued for the orchestrator/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/not run yet/i)).toBeInTheDocument();
  });

  it("queues now and cancels a task", async () => {
    api.triggerScheduledWork.mockResolvedValue({ ok: true });
    api.cancelScheduledWork.mockResolvedValue({ ok: true });
    harness.state.canvas = {
      jobs: [],
      steps: [],
      outcomes: [],
      scheduled_work: [task],
    } as unknown;

    render(<SchedulePanel />);

    fireEvent.click(screen.getByRole("button", { name: /queue now/i }));
    await waitFor(() => {
      expect(api.triggerScheduledWork).toHaveBeenCalledWith("work-1", "http://mcp");
    });

    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));
    await waitFor(() => {
      expect(api.cancelScheduledWork).toHaveBeenCalledWith("work-1", "http://mcp");
    });
  });
});
