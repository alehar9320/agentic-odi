import { render, screen, fireEvent, waitFor } from "@testing-library/react";
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

const mocks = vi.hoisted(() => ({
  updateStep: vi.fn(async () => undefined),
  deleteStep: vi.fn(async () => undefined),
  updateJob: vi.fn(async () => undefined),
  deleteJob: vi.fn(async () => undefined),
}));

vi.mock("../../state/StudioContext", () => ({
  useStudio: () => ({
    canvas: mockCanvasData,
    canvasLoading: false,
    addStep: vi.fn(),
    ...mocks,
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

  it("moves a focused step up with the arrow keys", async () => {
    mocks.updateStep.mockClear();
    render(<JobMap />);

    const rows = screen.getAllByRole("listitem");
    expect(rows).toHaveLength(2);

    rows[1].focus();
    expect(rows[1]).toHaveFocus();
    fireEvent.keyDown(rows[1], { key: "ArrowUp" });

    await waitFor(() => expect(mocks.updateStep).toHaveBeenCalledTimes(2));
    expect(mocks.updateStep).toHaveBeenNthCalledWith(1, "STEP-2", { order: 1 });
    expect(mocks.updateStep).toHaveBeenNthCalledWith(2, "STEP-1", { order: 2 });
  });

  it("ignores arrow keys that would move a step past the ends", () => {
    mocks.updateStep.mockClear();
    render(<JobMap />);

    const [first, last] = screen.getAllByRole("listitem");

    fireEvent.keyDown(first, { key: "ArrowUp" });
    fireEvent.keyDown(last, { key: "ArrowDown" });

    expect(mocks.updateStep).not.toHaveBeenCalled();
  });
});
