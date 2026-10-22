import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const studio = vi.hoisted(() => ({
  canvas: null as null | {
    jobs: { id: string }[];
    steps: { id: string }[];
    outcomes: { id: string; evidence?: string }[];
    source: "seed";
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
