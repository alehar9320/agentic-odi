import { render, screen, fireEvent } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { JobMap } from "./JobMap";

const mockCanvasData = {
  jobs: [{ id: "JOB-1", name: "Deploy Service" }],
  steps: [
    { id: "STEP-1", name: "Define payload parameters", order: 1 },
    { id: "STEP-2", name: "Locate target endpoint", order: 2 },
  ],
  outcomes: [],
  source: "seed" as const,
};

const harness = vi.hoisted(() => ({
  state: {
    canvasState: { kind: "ready", data: null } as unknown,
    refreshCanvas: vi.fn(),
    addStep: vi.fn(),
  },
}));

vi.mock("../../state/StudioContext", () => ({
  useStudio: () => harness.state,
}));

describe("JobMap Interactive Visualization", () => {
  beforeEach(() => {
    harness.state.canvasState = { kind: "ready", data: mockCanvasData };
  });

  it("renders 8 universal process phases", () => {
    render(<JobMap />);
    expect(screen.getByText("Universal Job Map (8 Process Phases)")).toBeInTheDocument();
    expect(screen.getAllByText("1. Define")[0]).toBeInTheDocument();
    expect(screen.getByText("8. Conclude")).toBeInTheDocument();
  });

  it("names the Ulwick phase on each step row", () => {
    render(<JobMap />);

    const row = screen.getByText("Define payload parameters").closest(".step-row");
    expect(row).toHaveTextContent("1. Define");
    expect(row).not.toHaveTextContent("Phase 1");
  });

  it("filters job steps when clicking a phase card", () => {
    render(<JobMap />);
    const phase1 = screen.getAllByText("1. Define")[0];
    fireEvent.click(phase1);

    expect(screen.getByText("Define payload parameters")).toBeInTheDocument();
  });
});

describe("JobMap failures", () => {
  it("does not render a zeroed map when the canvas failed", () => {
    harness.state.canvasState = {
      kind: "error",
      data: null,
      error: {
        code: "mcp_unreachable",
        message: "The MCP server is unreachable.",
        retryable: true,
      },
    };

    render(<JobMap />);

    expect(screen.getByRole("alert").textContent).toContain("The MCP server is unreachable.");
    expect(screen.queryByText("0 steps")).toBeNull();
  });
});
