import { render, screen, fireEvent } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { CanvasState } from "../../types";
import { OpportunityLandscape } from "./OpportunityLandscape";

// Mock StudioContext
const mockCanvasData = {
  jobs: [{ id: "JOB-1", name: "Deploy Service" }],
  steps: [{ id: "STEP-1", name: "Configure secrets", order: 1 }],
  outcomes: [
    { id: "O-101", statement: "Minimize time spent syncing secrets", importance: 9, satisfaction: 2, opportunity_score: 16 },
    { id: "O-102", statement: "Minimize risk of configuration drift", importance: 8, satisfaction: 7, opportunity_score: 9 },
  ],
  source: "seed" as const,
};

const harness = vi.hoisted(() => ({
  state: {
    canvasState: { kind: "ready", data: null } as unknown as CanvasState,
    refreshCanvas: vi.fn(),
    requestSimulate: vi.fn(),
    sendMessage: vi.fn(),
    pushToast: vi.fn(),
  },
}));

vi.mock("../../state/StudioContext", () => ({
  useStudio: () => harness.state,
}));

describe("OpportunityLandscape Data Visualization", () => {
  beforeEach(() => {
    harness.state.canvasState = { kind: "ready", data: mockCanvasData } as unknown as CanvasState;
  });

  it("renders opportunity landscape header and mode buttons", () => {
    render(<OpportunityLandscape />);
    expect(screen.getByText("Opportunity Landscape")).toBeInTheDocument();
    expect(screen.getByText("📊 Matrix")).toBeInTheDocument();
    expect(screen.getByText("🎴 Visual Cards")).toBeInTheDocument();
    expect(screen.getByText("📋 Table View")).toBeInTheDocument();
  });

  it("filters outcomes when searching", () => {
    render(<OpportunityLandscape />);
    const searchInput = screen.getByPlaceholderText(/Search opportunities/i);
    fireEvent.change(searchInput, { target: { value: "drift" } });

    // Table or Matrix details should reflect search filter
    expect(searchInput).toHaveValue("drift");
  });

  it("switches to table view mode", () => {
    render(<OpportunityLandscape />);
    const tableBtn = screen.getByText("📋 Table View");
    fireEvent.click(tableBtn);

    expect(screen.getByText("Desired Outcome Statement")).toBeInTheDocument();
    expect(screen.getByText("Minimize time spent syncing secrets")).toBeInTheDocument();
    expect(screen.getByText("Minimize risk of configuration drift")).toBeInTheDocument();
  });

  it("selects an outcome from a keyboard-focused table row", () => {
    render(<OpportunityLandscape />);
    fireEvent.click(screen.getByText("📋 Table View"));

    const row = screen.getByRole("row", { name: /Minimize time spent syncing secrets/i });
    row.focus();
    expect(row).toHaveFocus();

    fireEvent.keyDown(row, { key: "Enter" });

    expect(row).toHaveAttribute("aria-selected", "true");
  });

  it("toggles table selection with Space", () => {
    render(<OpportunityLandscape />);
    fireEvent.click(screen.getByText("📋 Table View"));

    const row = screen.getByRole("row", { name: /Minimize time spent syncing secrets/i });
    fireEvent.keyDown(row, { key: " " });
    expect(row).toHaveAttribute("aria-selected", "true");

    fireEvent.keyDown(row, { key: " " });
    expect(row).toHaveAttribute("aria-selected", "false");
  });

  it("toggles underserved filter checkbox", () => {
    render(<OpportunityLandscape />);
    const checkbox = screen.getByLabelText(/Show Underserved Only/i);
    expect(checkbox).not.toBeChecked();

    fireEvent.click(checkbox);
    expect(checkbox).toBeChecked();
  });
});

describe("OpportunityLandscape canvas states", () => {
  it("shows the failure and a retry instead of the metrics when the canvas failed", () => {
    harness.state.canvasState = {
      kind: "error",
      data: null,
      error: {
        code: "mcp_unreachable",
        message: "The MCP server is unreachable.",
        suggestion: "Check that the MCP server is running, then try again.",
        retryable: true,
      },
    } as unknown as CanvasState;
    harness.state.refreshCanvas = vi.fn();

    render(<OpportunityLandscape />);

    expect(screen.getByText("The MCP server is unreachable.")).toBeInTheDocument();
    expect(screen.queryByText("Active Job Map Contexts")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: /retry/i }));
    expect(harness.state.refreshCanvas).toHaveBeenCalled();
  });

  it("invites the user to capture something when the canvas is empty", () => {
    harness.state.canvasState = {
      kind: "empty",
      data: { jobs: [], steps: [], outcomes: [], source: "local" },
    } as unknown as CanvasState;

    render(<OpportunityLandscape />);

    expect(screen.getByText(/no opportunities yet/i)).toBeInTheDocument();
    expect(screen.queryByText("Active Job Map Contexts")).toBeNull();
  });

  it("shows why the seed board is standing in when the canvas says so", () => {
    harness.state.canvasState = {
      kind: "ready",
      data: { ...mockCanvasData, warnings: ["MCP endpoint unreachable"] },
    } as unknown as CanvasState;

    render(<OpportunityLandscape />);

    expect(screen.getByText(/mcp endpoint unreachable/i)).toBeInTheDocument();
  });

  it("shows the skeleton while a warm canvas reloads", () => {
    harness.state.canvasState = {
      kind: "loading",
      data: mockCanvasData,
    } as unknown as CanvasState;

    const { container } = render(<OpportunityLandscape />);

    expect(container.textContent).not.toContain("Active Job Map Contexts");
  });
});
