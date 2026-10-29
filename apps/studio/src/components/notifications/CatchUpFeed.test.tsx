import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import App from "../../App";
import type { StudioNotification } from "../../types";

vi.mock("../../api/studioApi", () => ({
  fetchConfig: vi.fn(async () => ({
    base_url: "http://localhost:8001/v1",
    api_key: "local",
    model_name: "local-tools-model",
    mcp_url: "http://localhost:8000/mcp",
  })),
  fetchCanvas: vi.fn(async () => ({
    jobs: [{ id: "JOB-1", name: "Deploy services" }],
    steps: [],
    outcomes: [],
    source: "local" as const,
  })),
  healthMcp: vi.fn(async () => ({ reachable: true })),
  healthLlm: vi.fn(async () => ({ healthy: true, message: "LLM backend reachable" })),
  addStep: vi.fn(async () => ({ ok: true })),
  addOutcome: vi.fn(async () => ({ ok: true })),
  createJob: vi.fn(async () => ({ ok: true, result: { id: "JOB-NEW" } })),
  updateJob: vi.fn(async () => ({ ok: true })),
  deleteJob: vi.fn(async () => ({ ok: true })),
  updateStep: vi.fn(async () => ({ ok: true })),
  deleteStep: vi.fn(async () => ({ ok: true })),
  updateOutcome: vi.fn(async () => ({ ok: true })),
  deleteOutcome: vi.fn(async () => ({ ok: true })),
  fetchMemory: vi.fn(async () => []),
  fetchConnectorCatalog: vi.fn(async () => []),
  fetchConnectors: vi.fn(async () => []),
  asStudioError: (error: unknown) => ({
    code: "internal",
    message: error instanceof Error ? error.message : "Something went wrong.",
    retryable: false,
  }),
  fetchLatestConversation: vi.fn(async () => ({ conversation: null, turns: [] })),
  createConversation: vi.fn(async () => ({
    id: "c-new",
    title: "",
    created_at: "2026-10-22T10:00:00+00:00",
    updated_at: "2026-10-22T10:00:00+00:00",
  })),
  addObservation: vi.fn(),
  updateObservation: vi.fn(),
  deleteObservation: vi.fn(async () => ({ ok: true })),
  clearMemory: vi.fn(async () => ({ ok: true })),
  streamChat: vi.fn(async () => undefined),
}));

const BRIEF = {
  product_name: "Ambient",
  target_user: "Platform engineers",
  job_statement: "Get a service from commit to production",
  core_problem: "A missed config key costs hours",
};

function seedNotifications(notifications: StudioNotification[]): void {
  window.localStorage.setItem("studio.notifications", JSON.stringify(notifications));
}

function notification(overrides: Partial<StudioNotification> = {}): StudioNotification {
  return {
    id: "NOTIF-1",
    title: "Opportunity Score Shift Identified",
    message: "An outcome was rescored.",
    category: "outcome",
    timestamp: new Date().toISOString(),
    read: false,
    simulated: false,
    ...overrides,
  };
}

beforeEach(() => {
  window.localStorage.clear();
  window.localStorage.setItem("studio.brief", JSON.stringify(BRIEF));
});

describe("Catch Up & Notification System", () => {
  it("starts with an honest empty feed instead of fabricated activity", async () => {
    render(<App />);

    const bellBtn = await screen.findByRole("button", { name: /catch up notifications/i });
    expect(within(bellBtn).queryByText("2")).toBeNull();

    fireEvent.click(bellBtn);

    expect(await screen.findByRole("heading", { name: /while you were away/i })).toBeInTheDocument();
    expect(screen.getByText(/no activity yet/i)).toBeInTheDocument();
    expect(screen.queryByText(/opportunity score shift identified/i)).toBeNull();
  });

  it("filters notifications by category", async () => {
    seedNotifications([
      notification(),
      notification({
        id: "NOTIF-2",
        title: "Friction Collapse Simulation Complete",
        category: "simulation",
        read: true,
      }),
    ]);
    render(<App />);

    fireEvent.click(await screen.findByRole("button", { name: /catch up notifications/i }));
    await screen.findByRole("heading", { name: /while you were away/i });

    fireEvent.click(screen.getByRole("tab", { name: /outcome shifts \(1\)/i }));

    expect(screen.getByText(/Opportunity Score Shift Identified/i)).toBeInTheDocument();
    expect(screen.queryByText(/Friction Collapse Simulation Complete/i)).toBeNull();
  });

  it("marks simulated events and keeps them out of the unread count", async () => {
    seedNotifications([
      notification({
        id: "NOTIF-SIM",
        title: "New Opportunity Uncovered",
        simulated: true,
      }),
    ]);
    render(<App />);

    const bellBtn = await screen.findByRole("button", { name: /catch up notifications/i });
    expect(within(bellBtn).queryByText("1")).toBeNull();

    fireEvent.click(bellBtn);
    await screen.findByRole("heading", { name: /while you were away/i });

    expect(screen.getByText(/new opportunity uncovered/i)).toBeInTheDocument();
    expect(screen.getByText(/^simulated$/i)).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /unread \(0\)/i })).toBeInTheDocument();
  });

  it("simulates a background system update on demand", async () => {
    render(<App />);

    fireEvent.click(await screen.findByRole("button", { name: /catch up notifications/i }));
    await screen.findByRole("heading", { name: /while you were away/i });

    const simBtn = screen.getByRole("button", { name: /\+ simulate update/i });
    fireEvent.click(simBtn);

    expect(await screen.findByText(/Background Activity:/i)).toBeInTheDocument();
    expect(screen.getByText(/^simulated$/i)).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /unread \(0\)/i })).toBeInTheDocument();
  });

  it("navigates to target workspace panel upon notification action", async () => {
    seedNotifications([
      notification({
        title: "Rescored outcome",
        targetPanel: "landscape",
        actionText: "View Landscape",
        chatPrompt: "Why did this outcome move?",
      }),
    ]);
    render(<App />);

    fireEvent.click(await screen.findByRole("button", { name: /catch up notifications/i }));
    await screen.findByRole("heading", { name: /while you were away/i });

    const actionBtn = screen.getAllByRole("button", { name: /view landscape →/i })[0];
    fireEvent.click(actionBtn);

    expect(await screen.findByRole("heading", { name: /opportunity landscape/i })).toBeInTheDocument();
  });
});
