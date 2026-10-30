import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { WorkPanel } from "./WorkPanel";

const api = vi.hoisted(() => ({
  listWorkItems: vi.fn(),
  getOrchestratorStatus: vi.fn(),
  cancelWorkItem: vi.fn(),
  retryWorkItem: vi.fn(),
}));

vi.mock("../../api/studioApi", () => ({
  listWorkItems: api.listWorkItems,
  getOrchestratorStatus: api.getOrchestratorStatus,
  cancelWorkItem: api.cancelWorkItem,
  retryWorkItem: api.retryWorkItem,
}));

const harness = vi.hoisted(() => ({
  state: {
    pushToast: vi.fn(),
    focusedSubject: null as { kind: string; id: string } | null,
  },
}));

vi.mock("../../state/StudioContext", () => ({
  useStudio: () => harness.state,
}));

const status = {
  daemon_running: true,
  heartbeat_at: "2026-10-29T12:00:00+00:00",
  pid: 123,
  queued: 1,
  running: 1,
  waiting_for_confirmation: 0,
  completed: 2,
  failed: 0,
  blocked: 0,
  cancelled: 0,
  targets: ["cloud"],
  db_path: "/tmp/orch.db",
  config_path: "/tmp/openhands.json",
};

const running = {
  work_item: {
    id: "work-1",
    work_key: "manual:1",
    source_kind: "manual" as const,
    title: "Fix the README",
    prompt: "do it",
    target_alias: "cloud",
    repository: "acme/repo",
    branch: "main",
    priority: 0,
    status: "running" as const,
    attempts: 1,
    next_attempt_at: null,
    job_id: null,
    metadata: {},
    created_at: "2026-10-29T11:00:00+00:00",
    updated_at: "2026-10-29T11:01:00+00:00",
  },
  latest_run: {
    id: "run-1",
    work_item_id: "work-1",
    attempt: 1,
    status: "running" as const,
    conversation_id: "conv-1",
    conversation_url: "https://cloud.test/conversations/conv-1",
    policy_verified: true,
    cost_usd: 1.25,
    tokens: 4200,
    summary: null,
    pr_urls: [],
    error: null,
    blocked_reason: null,
    approvals: 2,
    rejections: 0,
    started_at: "2026-10-29T11:00:00+00:00",
    finished_at: null,
    last_polled_at: "2026-10-29T11:01:00+00:00",
  },
};

const completed = {
  work_item: {
    ...running.work_item,
    id: "work-2",
    title: "Ship the fix",
    status: "completed" as const,
  },
  latest_run: {
    ...running.latest_run,
    id: "run-2",
    status: "completed" as const,
    summary: "Opened a pull request.",
    pr_urls: ["https://github.test/acme/repo/pull/9"],
    finished_at: "2026-10-29T11:30:00+00:00",
  },
};

beforeEach(() => {
  api.listWorkItems.mockReset();
  api.getOrchestratorStatus.mockReset();
  api.cancelWorkItem.mockReset();
  api.retryWorkItem.mockReset();
  harness.state.pushToast.mockReset();
  harness.state.focusedSubject = null;
  api.listWorkItems.mockResolvedValue({ work_items: [running, completed] });
  api.getOrchestratorStatus.mockResolvedValue({ status });
});

describe("WorkPanel", () => {
  it("shows the daemon state, queue counts, cost, and the real PR link", async () => {
    render(<WorkPanel />);

    expect(await screen.findByText("Fix the README")).toBeInTheDocument();
    expect(screen.getByText("daemon running")).toBeInTheDocument();
    expect(screen.getByText(/1 queued · 1 running/)).toBeInTheDocument();
    expect(screen.getByText(/2 completed/)).toBeInTheDocument();
    expect(
      screen.getAllByText(/\$1\.25 · 4,200 tokens · 2 approved/).length,
    ).toBeGreaterThan(0);
    expect(screen.getByRole("link", { name: "https://github.test/acme/repo/pull/9" })).toBeInTheDocument();
    expect(screen.getByText("Opened a pull request.")).toBeInTheDocument();
  });

  it("plans for a stopped daemon without pretending work is moving", async () => {
    api.getOrchestratorStatus.mockResolvedValue({
      status: { ...status, daemon_running: false },
    });

    render(<WorkPanel />);

    expect(await screen.findByText("daemon not running")).toBeInTheDocument();
    expect(screen.getByText(/Nothing dispatches while the daemon is stopped/)).toBeInTheDocument();
  });

  it("says how to queue work when the store is empty", async () => {
    api.listWorkItems.mockResolvedValue({ work_items: [] });

    render(<WorkPanel />);

    expect(await screen.findByText(/No work yet/)).toBeInTheDocument();
    expect(screen.getByText("odi orchestrate add")).toBeInTheDocument();
  });

  it("cancels an active item and refreshes", async () => {
    api.cancelWorkItem.mockResolvedValue({ ok: true });

    render(<WorkPanel />);
    fireEvent.click(await screen.findByRole("button", { name: /cancel/i }));

    await waitFor(() => {
      expect(api.cancelWorkItem).toHaveBeenCalledWith("work-1");
    });
    expect(api.listWorkItems).toHaveBeenCalledTimes(2);
  });

  it("retries a finished item", async () => {
    api.retryWorkItem.mockResolvedValue({ ok: true });

    render(<WorkPanel />);
    fireEvent.click(await screen.findByRole("button", { name: /retry/i }));

    await waitFor(() => {
      expect(api.retryWorkItem).toHaveBeenCalledWith("work-2");
    });
  });

  it("marks the work item a signal focused", async () => {
    harness.state.focusedSubject = { kind: "agent_work", id: "work-2" };

    render(<WorkPanel />);

    const title = await screen.findByText("Ship the fix");
    expect(title.closest("article")).toHaveClass("card--focused");
  });

  it("shows a load failure instead of an empty queue", async () => {
    api.listWorkItems.mockRejectedValue(new Error("sidecar offline"));

    render(<WorkPanel />);

    expect(await screen.findByText(/Could not load work: sidecar offline/)).toBeInTheDocument();
  });
});
