import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { JobStageDef } from "../../types";
import { JobMap } from "./JobMap";

/** The eight stages exactly as `GET /api/schema` returns them. */
export const SERVER_STAGES: JobStageDef[] = [
  { id: "define", name: "1. Define", description: "Determine goals and criteria" },
  { id: "locate", name: "2. Locate", description: "Gather inputs and resources" },
  { id: "prepare", name: "3. Prepare", description: "Set up context and workspace" },
  { id: "confirm", name: "4. Confirm", description: "Verify readiness to execute" },
  { id: "execute", name: "5. Execute", description: "Carry out core job work" },
  { id: "monitor", name: "6. Monitor", description: "Track performance and errors" },
  { id: "modify", name: "7. Modify", description: "Adjust inputs or workflows" },
  { id: "conclude", name: "8. Conclude", description: "Finish and store outputs" },
];

/**
 * The canonical stage vocabulary, mirroring `JOB_STAGE_ORDER` in
 * `packages/core/src/agentic_odi_core/models.py`. Kept here as the contract the
 * server fixture above must satisfy: dropping a stage from `SERVER_STAGES`
 * fails these tests rather than silently shrinking the map.
 */
const CANONICAL_STAGE_IDS = [
  "define",
  "locate",
  "prepare",
  "confirm",
  "execute",
  "monitor",
  "modify",
  "conclude",
];

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
  refreshStages: vi.fn(async () => undefined),
}));

const harness = vi.hoisted(() => ({
  state: {
    canvasState: { kind: "ready", data: null } as unknown,
    stagesState: { kind: "ready", data: null } as unknown,
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
    harness.state.stagesState = { kind: "ready", data: SERVER_STAGES };
    harness.state.focusedJobId = null;
    harness.state.addStep.mockClear();
  });

  it("renders the stages the server named, in the order the server sent them", () => {
    const { container } = render(<JobMap />);
    expect(screen.getByText("Universal Job Map")).toBeInTheDocument();

    const cards = Array.from(container.querySelectorAll(".jm-stage__name"));
    expect(cards.map((card) => card.textContent)).toEqual(
      SERVER_STAGES.map((stage) => stage.name),
    );
  });

  it("names the server stage on each step row", () => {
    render(<JobMap />);

    const row = screen.getByText("Define payload parameters").closest(".step-row");
    expect(row).toHaveTextContent("1. Define");
    expect(row).not.toHaveTextContent("Phase 1");
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

  it("stops offering a step once every supplied stage is filled", () => {
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

  it("filters job steps when clicking a stage card", () => {
    render(<JobMap />);
    const define = screen.getAllByText("1. Define")[0];
    fireEvent.click(define);

    expect(screen.getByText("Define payload parameters")).toBeInTheDocument();
  });

  it("exposes each stage card as a labelled toggle button", () => {
    render(<JobMap />);

    const stage = screen.getByRole("button", { name: "Filter steps by 1. Define" });
    expect(stage).toHaveAttribute("aria-pressed", "false");

    fireEvent.click(stage);
    expect(stage).toHaveAttribute("aria-pressed", "true");

    fireEvent.click(stage);
    expect(stage).toHaveAttribute("aria-pressed", "false");
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

  it("renders exactly a reduced and reordered fixture, proving it is not hardcoded", () => {
    harness.state.stagesState = {
      kind: "ready",
      data: [
        { id: "conclude", name: "Z. Conclude", description: "Finish and store outputs" },
        { id: "define", name: "A. Define", description: "Determine goals and criteria" },
        { id: "custom", name: "Custom Stage", description: "A stage the server invented" },
      ],
    };

    const { container } = render(<JobMap />);

    // Exactly the supplied stages, in the supplied order.
    const cards = Array.from(container.querySelectorAll(".jm-stage__name"));
    expect(cards.map((card) => card.textContent)).toEqual([
      "Z. Conclude",
      "A. Define",
      "Custom Stage",
    ]);
    // Stages the server did not name must not appear.
    expect(screen.queryByText("3. Prepare")).toBeNull();
    expect(screen.queryByText("5. Execute")).toBeNull();
  });

  it("writes nothing while rendering", () => {
    render(<JobMap />);

    expect(mocks.updateStep).not.toHaveBeenCalled();
    expect(mocks.deleteStep).not.toHaveBeenCalled();
    expect(mocks.updateJob).not.toHaveBeenCalled();
    expect(mocks.deleteJob).not.toHaveBeenCalled();
    expect(harness.state.addStep).not.toHaveBeenCalled();
  });
});

describe("JobMap stage contract", () => {
  it("carries the canonical eight stages, so a dropped one fails here", () => {
    expect(SERVER_STAGES.map((stage) => stage.id)).toEqual(CANONICAL_STAGE_IDS);
  });
});

describe("JobMap stage loading and failures", () => {
  beforeEach(() => {
    harness.state.canvasState = { kind: "ready", data: mockCanvasData };
    harness.state.stagesState = { kind: "ready", data: SERVER_STAGES };
  });

  it("shows a loading state before the stages arrive", () => {
    harness.state.stagesState = { kind: "loading", data: null };

    render(<JobMap />);

    expect(screen.getByText(/loading the job-map stages/i)).toBeInTheDocument();
  });

  it("renders the failure panel when the schema fetch fails", () => {
    harness.state.stagesState = {
      kind: "error",
      data: null,
      error: {
        code: "internal",
        message: "The schema request failed.",
        retryable: true,
      },
    };

    render(<JobMap />);

    expect(screen.getByRole("alert").textContent).toContain("The schema request failed.");
    expect(screen.queryByText("1. Define")).toBeNull();
  });

  it("retries the schema request from the failure panel", () => {
    mocks.refreshStages.mockClear();
    harness.state.stagesState = {
      kind: "error",
      data: null,
      error: { code: "internal", message: "The schema request failed.", retryable: true },
    };

    render(<JobMap />);
    fireEvent.click(screen.getByRole("button", { name: /retry/i }));

    expect(mocks.refreshStages).toHaveBeenCalledTimes(1);
  });

  it("shows the supplied stages even when the job has no steps yet", () => {
    harness.state.stagesState = { kind: "ready", data: SERVER_STAGES };
    harness.state.canvasState = {
      kind: "ready",
      data: { ...mockCanvasData, steps: [] },
    };

    const { container } = render(<JobMap />);

    const cards = Array.from(container.querySelectorAll(".jm-stage__name"));
    expect(cards.map((card) => card.textContent)).toEqual(
      SERVER_STAGES.map((stage) => stage.name),
    );
  });

  it("does not render a zeroed map when the canvas failed", () => {
    harness.state.stagesState = { kind: "ready", data: SERVER_STAGES };
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
