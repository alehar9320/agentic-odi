import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

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

vi.mock("../../state/StudioContext", () => ({
  useStudio: () => ({
    canvasState: { kind: "ready", data: mockCanvasData },
    refreshCanvas: vi.fn(),
    addStep: vi.fn(),
  }),
}));

describe("JobMap Interactive Visualization", () => {
  it("renders 8 universal process phases", () => {
    render(<JobMap />);
    expect(screen.getByText("Universal Job Map (8 Process Phases)")).toBeInTheDocument();
    expect(screen.getByText("1. Define")).toBeInTheDocument();
    expect(screen.getByText("8. Conclude")).toBeInTheDocument();
  });

  it("filters job steps when clicking a phase card", () => {
    render(<JobMap />);
    const phase1 = screen.getByText("1. Define");
    fireEvent.click(phase1);

    expect(screen.getByText("Define payload parameters")).toBeInTheDocument();
  });
});
