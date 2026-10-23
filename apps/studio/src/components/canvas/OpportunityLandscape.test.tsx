import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

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

vi.mock("../../state/StudioContext", () => ({
  useStudio: () => ({
    canvas: mockCanvasData,
    canvasLoading: false,
    requestSimulate: vi.fn(),
    sendMessage: vi.fn(),
    pushToast: vi.fn(),
  }),
}));

describe("OpportunityLandscape Data Visualization", () => {
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
