import { render, screen, fireEvent, waitFor } from "@testing-library/react";
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

const mocks = vi.hoisted(() => ({
  updateStep: vi.fn(async () => undefined),
  deleteStep: vi.fn(async () => undefined),
  updateJob: vi.fn(async () => undefined),
  deleteJob: vi.fn(async () => undefined),
}));

const harness = vi.hoisted(() => ({
  state: {
    canvasState: { kind: "ready", data: null } as unknown,
    refreshCanvas: vi.fn(),
    addStep: vi.fn(),
    ...mocks,
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

  it("moves a focused step down with the arrow keys", async () => {
    mocks.updateStep.mockClear();
    render(<JobMap />);

    const rows = screen.getAllByRole("listitem");
    expect(rows).toHaveLength(2);

    rows[0].focus();
    expect(rows[0]).toHaveFocus();
    fireEvent.keyDown(rows[0], { key: "ArrowDown" });

    await waitFor(() => expect(mocks.updateStep).toHaveBeenCalledTimes(2));
    expect(mocks.updateStep).toHaveBeenNthCalledWith(1, "STEP-1", { order: 2 });
    expect(mocks.updateStep).toHaveBeenNthCalledWith(2, "STEP-2", { order: 1 });
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
