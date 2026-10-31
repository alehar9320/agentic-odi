import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const studio = vi.hoisted(() => ({
  canvas: null as null | {
    jobs: { id: string }[];
    steps: { id: string; stage?: string | null }[];
    outcomes: { id: string; evidence?: string; step_id?: string | null }[];
    source: "seed" | "mcp" | "local";
    provenance?: {
      kind: "live" | "seed" | "empty";
      reason: string;
      generated_at: string;
      record_counts: { jobs: number; steps: number; outcomes: number; evidence: number };
    };
  },
  memory: [] as { id: string; text: string }[],
  activePanel: null as string | null,
  openPanel: vi.fn(),
  closePanel: vi.fn(),
}));

vi.mock("../../state/StudioContext", () => ({
  useStudio: () => studio,
}));

import { WorkbenchRail } from "./WorkbenchRail";

function canvas(overrides: Partial<NonNullable<typeof studio.canvas>> = {}) {
  return {
    jobs: [],
    steps: [],
    outcomes: [],
    source: "seed" as const,
    ...overrides,
  };
}

describe("WorkbenchRail", () => {
  beforeEach(() => {
    studio.canvas = null;
    studio.memory = [];
    studio.activePanel = null;
    studio.openPanel.mockClear();
    studio.closePanel.mockClear();
  });

  it("stays out of the way until the thread has made something", () => {
    render(<WorkbenchRail />);

    expect(screen.queryByRole("navigation", { name: /your work/i })).toBeNull();
  });

  it("derives its items and counts from the canvas", () => {
    studio.canvas = canvas({
      outcomes: [{ id: "O-1", evidence: "a quote" }, { id: "O-2" }],
      steps: [{ id: "S-1" }],
    });

    render(<WorkbenchRail />);

    expect(screen.getByRole("button", { name: "Landscape, 2 opportunities" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Job map, 1 step" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Evidence, 1 signal" })).toBeInTheDocument();
  });

  it("counts covered stages, not steps, in the coverage chip", () => {
    studio.canvas = canvas({
      // Eight steps but only one stage carries a staged outcome: coverage is
      // one stage, and the chip must not report the step count as coverage.
      steps: [
        { id: "S-1", stage: "define" },
        { id: "S-2", stage: "locate" },
        { id: "S-3", stage: "prepare" },
      ],
      outcomes: [{ id: "O-1", step_id: "S-1" }, { id: "O-2", step_id: "S-1" }],
    });

    render(<WorkbenchRail />);

    expect(screen.getByRole("button", { name: "Coverage, 1 stage" })).toBeInTheDocument();
  });

  it("omits coverage when no outcome is staged", () => {
    studio.canvas = canvas({
      steps: [{ id: "S-1", stage: "define" }],
      outcomes: [{ id: "O-1" }, { id: "O-2" }],
    });

    render(<WorkbenchRail />);

    // Both outcomes are unstaged, so no stage holds an outcome: the job map
    // shows but coverage has nothing to report yet.
    expect(screen.getByRole("button", { name: "Job map, 1 step" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^coverage/i })).toBeNull();
  });

  it("shows what the agent has learned once it has a note", () => {
    studio.canvas = canvas();
    studio.memory = [
      { id: "o-1", text: "Owns activation." },
      { id: "o-2", text: "Prefers short updates." },
    ];

    render(<WorkbenchRail />);

    fireEvent.click(screen.getByRole("button", { name: "What I know, 2 notes" }));
    expect(studio.openPanel).toHaveBeenCalledWith("memory");
  });

  it("omits a view that has nothing to show", () => {
    studio.canvas = canvas({ outcomes: [{ id: "O-1" }] });

    render(<WorkbenchRail />);

    expect(screen.queryByRole("button", { name: /job map/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /evidence/i })).toBeNull();
  });

  it("labels a seed canvas as sample data", () => {
    studio.canvas = canvas({
      outcomes: [{ id: "O-1" }],
      provenance: {
        kind: "seed",
        reason: "mcp_unreachable",
        generated_at: "2026-10-29T10:00:00+00:00",
        record_counts: { jobs: 1, steps: 8, outcomes: 5, evidence: 0 },
      },
    });

    render(<WorkbenchRail />);

    expect(screen.getByText("OFFLINE")).toBeInTheDocument();
  });

  it("labels a demo seed differently from an unreachable server", () => {
    studio.canvas = canvas({
      outcomes: [{ id: "O-1" }],
      provenance: {
        kind: "seed",
        reason: "demo",
        generated_at: "2026-10-29T10:00:00+00:00",
        record_counts: { jobs: 1, steps: 8, outcomes: 5, evidence: 0 },
      },
    });

    render(<WorkbenchRail />);

    expect(screen.getByText("DEMO")).toBeInTheDocument();
    expect(screen.queryByText("OFFLINE")).toBeNull();
  });

  it("shows no provenance chip for a live canvas", () => {
    studio.canvas = canvas({
      source: "mcp",
      outcomes: [{ id: "O-1" }],
      provenance: {
        kind: "live",
        reason: "mcp_live",
        generated_at: "2026-10-29T10:00:00+00:00",
        record_counts: { jobs: 1, steps: 1, outcomes: 1, evidence: 0 },
      },
    });

    render(<WorkbenchRail />);

    expect(screen.queryByText("DEMO")).toBeNull();
    expect(screen.queryByText("OFFLINE")).toBeNull();
  });

  it("opens a view and closes it again from the same chip", () => {
    studio.canvas = canvas({ outcomes: [{ id: "O-1" }] });

    const { rerender } = render(<WorkbenchRail />);
    fireEvent.click(screen.getByRole("button", { name: /^landscape/i }));

    expect(studio.openPanel).toHaveBeenCalledWith("landscape");

    studio.activePanel = "landscape";
    rerender(<WorkbenchRail />);

    const chip = screen.getByRole("button", { name: /^landscape/i });
    expect(chip).toHaveAttribute("aria-current", "page");
    fireEvent.click(chip);

    expect(studio.closePanel).toHaveBeenCalled();
  });
});
