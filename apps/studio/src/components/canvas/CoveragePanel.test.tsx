import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { CoverageReport, JobStageDef } from "../../types";
import { CoveragePanel } from "./CoveragePanel";

const STAGES: JobStageDef[] = [
  { id: "define", name: "1. Define", description: "Determine goals" },
  { id: "locate", name: "2. Locate", description: "Gather inputs" },
  { id: "prepare", name: "3. Prepare", description: "Set up" },
  { id: "confirm", name: "4. Confirm", description: "Verify" },
  { id: "execute", name: "5. Execute", description: "Carry out" },
  { id: "monitor", name: "6. Monitor", description: "Track" },
  { id: "modify", name: "7. Modify", description: "Adjust" },
  { id: "conclude", name: "8. Conclude", description: "Finish" },
];

/** A report where only Define and Locate have outcomes. */
const REPORT: CoverageReport = {
  job_id: "JOB-1",
  per_stage: [
    { stage: "define", outcomes: 3, measured: 2, quotes: 4 },
    { stage: "locate", outcomes: 1, measured: 1, quotes: 1 },
    { stage: "prepare", outcomes: 0, measured: 0, quotes: 0 },
    { stage: "confirm", outcomes: 0, measured: 0, quotes: 0 },
    { stage: "execute", outcomes: 0, measured: 0, quotes: 0 },
    { stage: "monitor", outcomes: 0, measured: 0, quotes: 0 },
    { stage: "modify", outcomes: 0, measured: 0, quotes: 0 },
    { stage: "conclude", outcomes: 0, measured: 0, quotes: 0 },
  ],
  totals: {
    outcomes: 4,
    measured: 3,
    quotes: 5,
    unassigned_outcomes: 0,
    unassigned_measured: 0,
    unassigned_quotes: 0,
  },
  gaps: ["prepare", "confirm", "execute", "monitor", "modify", "conclude"],
};

const mocks = vi.hoisted(() => ({ refreshCoverage: vi.fn(async () => undefined) }));

const harness = vi.hoisted(() => ({
  state: {
    canvasState: { kind: "ready", data: { jobs: [{ id: "JOB-1", name: "Onboard" }], steps: [] } },
    stagesState: { kind: "ready", data: [] as unknown },
    coverageState: { kind: "ready", data: null } as unknown,
    ...mocks,
  },
}));

vi.mock("../../state/StudioContext", () => ({
  useStudio: () => harness.state,
}));

describe("CoveragePanel", () => {
  beforeEach(() => {
    harness.state.canvasState = {
      kind: "ready",
      data: { jobs: [{ id: "JOB-1", name: "Onboard" }], steps: [] },
    };
    harness.state.stagesState = { kind: "ready", data: STAGES };
    harness.state.coverageState = { kind: "ready", data: REPORT };
    mocks.refreshCoverage.mockClear();
  });

  it("renders every stage as a row, empty ones included", () => {
    const { container } = render(<CoveragePanel />);

    const rows = Array.from(container.querySelectorAll(".cov-table tbody tr"));
    expect(rows).toHaveLength(8);
    expect(rows.map((row) => row.getAttribute("data-covered"))).toEqual([
      "yes",
      "yes",
      "no",
      "no",
      "no",
      "no",
      "no",
      "no",
    ]);
  });

  it("names the gaps instead of hiding them", () => {
    render(<CoveragePanel />);

    expect(screen.getByText(/Not yet covered:/)).toHaveTextContent(
      "3. Prepare, 4. Confirm, 5. Execute, 6. Monitor, 7. Modify, 8. Conclude",
    );
  });

  it("shows the totals and the explicit unassigned bucket", () => {
    render(<CoveragePanel />);

    expect(screen.getByText(/Outcomes 4/)).toBeInTheDocument();
    expect(screen.getByText(/Unassigned: 0 outcomes, 0 quotes/)).toBeInTheDocument();
  });

  it("shows a failure panel rather than a reassuring zeroed report", () => {
    harness.state.coverageState = {
      kind: "error",
      error: { message: "coverage unavailable", suggestion: null, code: null, status: 500 },
    };

    render(<CoveragePanel />);

    expect(screen.getByText(/coverage unavailable/)).toBeInTheDocument();
    expect(screen.queryByText(/Not yet covered:/)).not.toBeInTheDocument();
  });
});
