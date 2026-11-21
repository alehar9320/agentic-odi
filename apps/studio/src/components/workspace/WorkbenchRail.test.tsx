import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const studio = vi.hoisted(() => ({
  canvas: null as null | {
    jobs: { id: string }[];
    steps: { id: string }[];
    outcomes: { id: string; evidence?: string }[];
    evidence?: { id: string }[];
    source: "seed" | "mcp" | "local";
    provenance?: {
      kind: "live" | "seed" | "empty";
      reason: string;
      generated_at: string;
      record_counts: { jobs: number; steps: number; outcomes: number; evidence: number };
    };
  },
  memory: [] as { id: string; text: string }[],
  segments: [] as { id: string }[],
  activePanel: null as string | null,
  openPanel: vi.fn(),
  closePanel: vi.fn(),
}));

vi.mock("../../state/StudioContext", () => ({
  useStudio: () => studio,
}));

const panels = vi.hoisted(() => ({ blankBlurbs: false }));

vi.mock("./panels", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./panels")>();
  return {
    ...actual,
    findPanel: (id: string) => {
      const panel = actual.findPanel(id as never);
      return panels.blankBlurbs ? { ...panel, blurb: "   " } : panel;
    },
  };
});

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
    studio.segments = [];
    studio.activePanel = null;
    studio.openPanel.mockClear();
    studio.closePanel.mockClear();
    panels.blankBlurbs = false;
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

    expect(screen.getByRole("button", { name: "Where to focus, 2 opportunities" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Steps in the job, 1 step" })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "What customers said, 1 signal" }),
    ).toBeInTheDocument();
  });

  it("takes focus when it is activated, so the lens it opens can give it back (#810)", () => {
    studio.canvas = canvas({ outcomes: [{ id: "O-1" }] });
    render(<WorkbenchRail />);

    // The caret is somewhere else — on an empty stage, that is the composer.
    const elsewhere = document.createElement("input");
    document.body.append(elsewhere);
    elsewhere.focus();

    const chip = screen.getByRole("button", { name: "Where to focus, 1 opportunity" });
    fireEvent.click(chip);

    expect(studio.openPanel).toHaveBeenCalledWith("landscape");
    expect(chip).toHaveFocus();
    elsewhere.remove();
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

  it("counts the segments the outcomes support", () => {
    studio.canvas = canvas({ outcomes: [{ id: "O-1" }, { id: "O-2" }] });
    studio.segments = [{ id: "seg-1" }, { id: "seg-2" }, { id: "seg-3" }];

    render(<WorkbenchRail />);

    fireEvent.click(screen.getByRole("button", { name: "Who this is for, 3 segments" }));
    expect(studio.openPanel).toHaveBeenCalledWith("segments");
  });

  it("omits a view that has nothing to show", () => {
    studio.canvas = canvas({ outcomes: [{ id: "O-1" }] });

    render(<WorkbenchRail />);

    expect(screen.queryByRole("button", { name: /steps in the job/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /what customers said/i })).toBeNull();
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

  it("counts every stored record, not only the outcomes with a note", () => {
    studio.canvas = canvas({
      jobs: [{ id: "J-1" }],
      steps: [{ id: "S-1" }],
      outcomes: [{ id: "O-1" }, { id: "O-2", evidence: "a quote" }],
      evidence: [{ id: "E-1" }],
    });

    render(<WorkbenchRail />);

    expect(screen.getByRole("button", { name: "Records, 5 records" })).toBeInTheDocument();
  });

  it("opens the records lens from its chip", () => {
    studio.canvas = canvas({ outcomes: [{ id: "O-1" }] });

    render(<WorkbenchRail />);

    fireEvent.click(screen.getByRole("button", { name: "Records, 1 record" }));
    expect(studio.openPanel).toHaveBeenCalledWith("records");
  });

  it("keeps the records chip away while nothing is stored", () => {
    studio.canvas = canvas({ source: "mcp" });

    render(<WorkbenchRail />);

    expect(screen.queryByRole("button", { name: /records/i })).toBeNull();
  });

  it("opens a view and closes it again from the same chip", () => {
    studio.canvas = canvas({ outcomes: [{ id: "O-1" }] });

    const { rerender } = render(<WorkbenchRail />);
    fireEvent.click(screen.getByRole("button", { name: /^where to focus/i }));

    expect(studio.openPanel).toHaveBeenCalledWith("landscape");

    studio.activePanel = "landscape";
    rerender(<WorkbenchRail />);

    const chip = screen.getByRole("button", { name: /^where to focus/i });
    expect(chip).toHaveAttribute("aria-current", "page");
    fireEvent.click(chip);

    expect(studio.closePanel).toHaveBeenCalled();
  });
  it("says on hover what a chip opens (#696)", () => {
    studio.canvas = canvas({ outcomes: [{ id: "O-1" }] });
    render(<WorkbenchRail />);

    const chip = screen.getByRole("button", { name: /^where to focus/i });
    fireEvent.mouseEnter(chip);

    expect(screen.getByRole("tooltip")).toHaveTextContent(
      "Every outcome scored. Anything above 10 is underserved.",
    );

    fireEvent.mouseLeave(chip);
    expect(screen.queryByRole("tooltip")).toBeNull();
  });

  it("says it on focus too, without changing the count in the name (#696)", () => {
    studio.canvas = canvas({ outcomes: [{ id: "O-1" }] });
    render(<WorkbenchRail />);

    const chip = screen.getByRole("button", { name: "Where to focus, 1 opportunity" });
    fireEvent.focus(chip);

    expect(screen.getByRole("tooltip")).toHaveTextContent(/every outcome scored/i);
    expect(chip).toHaveAccessibleName("Where to focus, 1 opportunity");

    fireEvent.blur(chip);
    expect(screen.queryByRole("tooltip")).toBeNull();
  });

  it("falls back to the chip's own label when the lens has no blurb (#696)", () => {
    panels.blankBlurbs = true;
    studio.canvas = canvas({ outcomes: [{ id: "O-1" }] });
    render(<WorkbenchRail />);

    fireEvent.mouseEnter(screen.getByRole("button", { name: /^where to focus/i }));

    expect(screen.getByRole("tooltip")).toHaveTextContent(/^Where to focus$/);
  });

});
