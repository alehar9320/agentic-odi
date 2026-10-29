import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { JOB_STAGES } from "../../domain/jobStages";
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
    focusedJobId: null as string | null,
    ...mocks,
  },
}));

vi.mock("../../state/StudioContext", () => ({
  useStudio: () => harness.state,
}));

describe("JobMap Interactive Visualization", () => {
  beforeEach(() => {
    harness.state.canvasState = { kind: "ready", data: mockCanvasData };
    harness.state.focusedJobId = null;
  });

  it("renders 8 universal process phases", () => {
    render(<JobMap />);
    expect(screen.getByText("Universal Job Map (8 Process Phases)")).toBeInTheDocument();
    expect(screen.getAllByText("1. Define")[0]).toBeInTheDocument();
    expect(screen.getByText("8. Conclude")).toBeInTheDocument();
  });

  it("renders the stage descriptions from the shared constant, with no second copy", () => {
    render(<JobMap />);

    for (const stage of JOB_STAGES) {
      expect(screen.getByText(stage.desc)).toBeInTheDocument();
    }
  });

  it("follows the job a signal points at", () => {
    harness.state.canvasState = {
      kind: "ready",
      data: {
        jobs: [
          { id: "JOB-1", name: "Deploy Service" },
          { id: "JOB-2", name: "Review contracts" },
        ],
        steps: [{ id: "STEP-9", job_id: "JOB-2", name: "Sign the renewal", order: 1 }],
        outcomes: [],
        source: "seed" as const,
      },
    };
    harness.state.focusedJobId = "JOB-2";

    render(<JobMap />);

    expect(screen.getByRole("combobox", { name: "Job" })).toHaveValue("JOB-2");
    expect(screen.getByText("Sign the renewal")).toBeInTheDocument();
  });

  it("names the Ulwick phase on each step row", () => {
    render(<JobMap />);

    const row = screen.getByText("Define payload parameters").closest(".step-row");
    expect(row).toHaveTextContent("1. Define");
    expect(row).not.toHaveTextContent("Phase 1");
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

  it("stops offering a step once the eight phases are filled", () => {
    harness.state.canvasState = {
      kind: "ready",
      data: {
        ...mockCanvasData,
        steps: Array.from({ length: 8 }, (_, index) => ({
          id: `STEP-${index + 1}`,
          name: `Step ${index + 1}`,
          order: index + 1,
        })),
      },
    };
    render(<JobMap />);

    expect(screen.queryByRole("button", { name: /add step/i })).toBeNull();
  });

  it("filters job steps when clicking a phase card", () => {
    render(<JobMap />);
    const phase1 = screen.getAllByText("1. Define")[0];
    fireEvent.click(phase1);

    expect(screen.getByText("Define payload parameters")).toBeInTheDocument();
  });

  it("exposes each phase card as a labelled toggle button", () => {
    render(<JobMap />);

    const phase = screen.getByRole("button", { name: "Filter steps by 1. Define" });
    expect(phase).toHaveAttribute("aria-pressed", "false");

    fireEvent.click(phase);
    expect(phase).toHaveAttribute("aria-pressed", "true");

    fireEvent.click(phase);
    expect(phase).toHaveAttribute("aria-pressed", "false");
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
