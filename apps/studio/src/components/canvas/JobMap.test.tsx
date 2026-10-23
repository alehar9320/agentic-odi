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
    expect(screen.getByText("1. Define")).toBeInTheDocument();
    expect(screen.getByText("8. Conclude")).toBeInTheDocument();
  });

  it("adds a step from the inline form", async () => {
    harness.state.addStep.mockResolvedValue(undefined);
    render(<JobMap />);

    fireEvent.click(screen.getByRole("button", { name: /add step/i }));
    fireEvent.change(screen.getByLabelText(/new step name/i), {
      target: { value: "Confirm the deployment target" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^save$/i }));

    await screen.findByRole("button", { name: /add step/i });
    expect(harness.state.addStep).toHaveBeenCalledWith({
      job_id: "JOB-1",
      name: "Confirm the deployment target",
      order: 3,
    });
  });

  it("filters job steps when clicking a phase card", () => {
    render(<JobMap />);
    const phase1 = screen.getByText("1. Define");
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
