import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import App from "../../App";

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

beforeEach(() => {
  window.localStorage.clear();
  window.localStorage.setItem("studio.brief", JSON.stringify(BRIEF));
});

describe("Catch Up & Notification System", () => {
  it("renders the bell icon in header with unread count and opens Catch Up panel", async () => {
    render(<App />);

    const bellBtn = await screen.findByRole("button", { name: /catch up notifications/i });
    expect(bellBtn).toBeInTheDocument();
    // Default seed notifications include 2 unread
    expect(within(bellBtn).getByText("2")).toBeInTheDocument();

    fireEvent.click(bellBtn);

    expect(await screen.findByRole("heading", { name: /while you were away/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /unread \(2\)/i })).toBeInTheDocument();
  });

  it("filters notifications by status and category", async () => {
    render(<App />);

    fireEvent.click(await screen.findByRole("button", { name: /catch up notifications/i }));
    await screen.findByRole("heading", { name: /while you were away/i });

    const unreadTab = screen.getByRole("tab", { name: /unread \(2\)/i });
    fireEvent.click(unreadTab);

    expect(screen.getByText(/Opportunity Score Shift Identified/i)).toBeInTheDocument();
    expect(screen.getByText(/Friction Collapse Simulation Complete/i)).toBeInTheDocument();
    expect(screen.queryByText(/New Customer Telemetry Signal/i)).toBeNull();
  });

  it("marks all notifications as read when requested", async () => {
    render(<App />);

    fireEvent.click(await screen.findByRole("button", { name: /catch up notifications/i }));
    await screen.findByRole("heading", { name: /while you were away/i });

    const markAllBtn = screen.getByRole("button", { name: /mark all as read/i });
    fireEvent.click(markAllBtn);

    await waitFor(() => {
      expect(screen.getByRole("tab", { name: /unread \(0\)/i })).toBeInTheDocument();
    });
  });

  it("simulates a background system update on demand", async () => {
    render(<App />);

    fireEvent.click(await screen.findByRole("button", { name: /catch up notifications/i }));
    await screen.findByRole("heading", { name: /while you were away/i });

    const simBtn = screen.getByRole("button", { name: /\+ simulate update/i });
    fireEvent.click(simBtn);

    expect(await screen.findByText(/Background Activity:/i)).toBeInTheDocument();
  });

  it("navigates to target workspace panel upon notification action", async () => {
    render(<App />);

    fireEvent.click(await screen.findByRole("button", { name: /catch up notifications/i }));
    await screen.findByRole("heading", { name: /while you were away/i });

    const actionBtn = screen.getAllByRole("button", { name: /view landscape →/i })[0];
    fireEvent.click(actionBtn);

    expect(await screen.findByRole("heading", { name: /opportunity landscape/i })).toBeInTheDocument();
  });
});
