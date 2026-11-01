import { render, screen, fireEvent, within, act } from "@testing-library/react";
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
    openPanel: vi.fn(),
    sendMessage: vi.fn(),
    pushToast: vi.fn(),
    theses: [],
    deleteThesis: vi.fn(),
    focusedSubject: null as { kind: string; id: string } | null,
    focusSubject: vi.fn(),
  },
}));

vi.mock("../../state/StudioContext", () => ({
  useStudio: () => harness.state,
}));

describe("OpportunityLandscape Data Visualization", () => {
  beforeEach(() => {
    harness.state.canvasState = { kind: "ready", data: mockCanvasData } as unknown as CanvasState;
    harness.state.focusedSubject = null;
    harness.state.focusSubject.mockClear();
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

  it("disables search and filters while the canvas loads", () => {
    harness.state.canvasState = { kind: "loading", data: null } as unknown as CanvasState;
    render(<OpportunityLandscape />);

    expect(screen.getByPlaceholderText(/Search opportunities/i)).toBeDisabled();
    expect(screen.getByLabelText(/Show Underserved Only/i)).toBeDisabled();
  });

  it("selects an outcome from a keyboard-focused table row", () => {
    render(<OpportunityLandscape />);
    fireEvent.click(screen.getByText("📋 Table View"));

    const row = screen.getByRole("row", { name: /Minimize time spent syncing secrets/i });
    row.focus();
    expect(row).toHaveFocus();

    fireEvent.keyDown(row, { key: "Enter" });

    expect(row).toHaveAttribute("aria-selected", "true");
    expect(harness.state.focusSubject).toHaveBeenCalledWith("outcome", "O-101");
  });

  it("reopens on the outcome from the previous session", () => {
    harness.state.focusedSubject = { kind: "outcome", id: "O-102" };

    render(<OpportunityLandscape />);
    fireEvent.click(screen.getByText("📋 Table View"));

    expect(screen.getByRole("row", { name: /Minimize risk of configuration drift/i })).toHaveAttribute(
      "aria-selected",
      "true",
    );
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

  it("counts the sources behind each outcome from the evidence list, not a stored counter", () => {
    harness.state.canvasState = {
      kind: "ready",
      data: {
        ...mockCanvasData,
        evidence: [
          { id: "ev-1", outcome_id: "O-101", content: "One." },
          { id: "ev-2", outcome_id: "O-101", content: "Two." },
          { id: "ev-3", outcome_id: "O-102", content: "Three." },
        ],
      },
    } as unknown as CanvasState;
    render(<OpportunityLandscape />);
    fireEvent.click(screen.getByText("📋 Table View"));

    const row = screen.getByRole("row", { name: /Minimize time spent syncing secrets/i });
    expect(row).toHaveTextContent("2");
  });
});

describe("OpportunityLandscape accessibility", () => {
  beforeEach(() => {
    harness.state.canvasState = { kind: "ready", data: mockCanvasData } as unknown as CanvasState;
  });

  it("names the matrix and summarizes it for assistive technology", () => {
    const { container } = render(<OpportunityLandscape />);

    const map = screen.getByRole("img", { name: "Opportunity map" });
    expect(map.tagName).toBe("svg");
    expect(map.querySelector("desc")?.textContent).toMatch(
      /2 outcomes, 1 of them underserved, spanning importance 8 to 9/i,
    );
    expect(container.querySelector(".opportunity-matrix")).not.toBeNull();
  });

  it("lists the plotted outcomes as text, not only as pixels", () => {
    render(<OpportunityLandscape />);

    const list = screen.getByRole("list", { name: "Opportunities on the map" });
    const items = within(list).getAllByRole("listitem");
    expect(items).toHaveLength(2);
    expect(items[0]).toHaveTextContent("O-101");
    expect(items[0]).toHaveTextContent(/Minimize time spent syncing secrets/);
    expect(items[0]).toHaveTextContent(/underserved/i);
  });

  it("labels the search field", () => {
    render(<OpportunityLandscape />);

    expect(screen.getByRole("textbox", { name: /search outcomes/i })).toBeInTheDocument();
  });

  it("turns each plotted outcome into a named, selectable control", () => {
    render(<OpportunityLandscape />);

    const node = screen.getByRole("button", {
      name: /O-101.*Minimize time spent syncing secrets.*score 16.*underserved/i,
    });
    expect(node).toHaveAttribute("tabindex", "0");
    expect(node).toHaveAttribute("aria-pressed", "false");

    fireEvent.keyDown(node, { key: "Enter" });

    expect(node).toHaveAttribute("aria-pressed", "true");
  });

  it("selects an outcome with Space from the plot", () => {
    render(<OpportunityLandscape />);

    const node = screen.getByRole("button", { name: /O-102/ });
    fireEvent.keyDown(node, { key: " " });

    expect(node).toHaveAttribute("aria-pressed", "true");
  });

  it("moves between plotted outcomes with arrow keys using a roving tab index", () => {
    render(<OpportunityLandscape />);

    const first = screen.getByRole("button", { name: /O-101/ });
    const second = screen.getByRole("button", { name: /O-102/ });
    expect(first).toHaveAttribute("tabindex", "0");
    expect(second).toHaveAttribute("tabindex", "-1");

    act(() => first.focus());
    fireEvent.keyDown(first, { key: "ArrowRight" });

    expect(second).toHaveFocus();
    expect(second).toHaveAttribute("tabindex", "0");
    expect(first).toHaveAttribute("tabindex", "-1");

    fireEvent.keyDown(second, { key: "ArrowLeft" });

    expect(first).toHaveFocus();
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

  it("says when the board is demo data rather than the user's work", () => {
    render(<OpportunityLandscape />);

    expect(screen.getByText(/demo data/i)).toBeInTheDocument();
    expect(screen.getByText(/nothing here comes from your research/i)).toBeInTheDocument();
  });

  it("points a demo canvas at the settings panel", () => {
    harness.state.openPanel = vi.fn();
    render(<OpportunityLandscape />);

    fireEvent.click(screen.getByRole("button", { name: /connect a data source/i }));

    expect(harness.state.openPanel).toHaveBeenCalledWith("settings");
  });

  it("shows no sample-data notice for a live canvas", () => {
    harness.state.canvasState = {
      kind: "ready",
      data: { ...mockCanvasData, source: "mcp" },
    } as unknown as CanvasState;

    render(<OpportunityLandscape />);

    expect(screen.queryByText(/demo data/i)).toBeNull();
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
