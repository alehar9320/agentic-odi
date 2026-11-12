import { act, fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { CanvasState } from "../../types";
import { OpportunityLandscape } from "./OpportunityLandscape";

// The third cold-open segment: the SPA's first interactive render on the
// reference study (1,500 outcomes). The fix caps how many outcomes the matrix
// plots above the fold; this test asserts the shape of that fix — the plot
// stays bounded while every outcome remains reachable — rather than a
// wall-clock number, which a shared CI box cannot make stable. The measured
// before/after figures are recorded in docs/development.md.
const REFERENCE_OUTCOMES = 1500;
const MATRIX_POINT_LIMIT = 200;

function bigCanvas() {
  const outcomes = Array.from({ length: REFERENCE_OUTCOMES }, (_, i) => ({
    id: `OUT-${i}`,
    job_id: `JOB-${i % 30}`,
    statement: `Minimize the time it takes to finish study task ${i} when working`,
    importance: 1 + (i % 10),
    satisfaction: 1 + ((i * 7) % 10),
    opportunity_score:
      1 + (i % 10) + Math.max(1 + (i % 10) - (1 + ((i * 7) % 10)), 0),
  }));
  return {
    jobs: Array.from({ length: 30 }, (_, i) => ({ id: `JOB-${i}`, name: `Job ${i}` })),
    steps: [],
    outcomes,
    evidence: [],
    source: "local" as const,
  };
}

const harness = vi.hoisted(() => ({
  state: {
    canvasState: { kind: "ready", data: null } as unknown as CanvasState,
    refreshCanvas: vi.fn(),
    openPanel: vi.fn(),
    theses: [],
    deleteThesis: vi.fn(),
    focusedSubject: null,
    focusSubject: vi.fn(),
  },
}));

vi.mock("../../state/StudioContext", () => ({ useStudio: () => harness.state }));

describe("OpportunityLandscape at study scale", () => {
  it("bounds the plotted points but keeps every outcome in the summary", () => {
    harness.state.canvasState = { kind: "ready", data: bigCanvas() } as unknown as CanvasState;

    const { container } = render(<OpportunityLandscape />);

    const plotted = container.querySelectorAll(".matrix-node");
    expect(plotted.length).toBe(MATRIX_POINT_LIMIT);

    // The summary still describes the whole study, not just the plotted head.
    const desc = container.querySelector("#opportunity-map-desc");
    expect(desc?.textContent).toMatch(
      new RegExp(`^${REFERENCE_OUTCOMES} outcomes,`),
    );
  });

  it("plots every outcome once the reader asks for all of them", () => {
    harness.state.canvasState = { kind: "ready", data: bigCanvas() } as unknown as CanvasState;

    const { container } = render(<OpportunityLandscape />);
    expect(container.querySelectorAll(".matrix-node").length).toBe(MATRIX_POINT_LIMIT);

    act(() => {
      fireEvent.click(screen.getByRole("button", { name: /plot all/i }));
    });

    expect(container.querySelectorAll(".matrix-node").length).toBe(REFERENCE_OUTCOMES);
  });
});
