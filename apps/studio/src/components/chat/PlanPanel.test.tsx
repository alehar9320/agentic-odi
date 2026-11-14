import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import type { CanvasState } from "../../types";

const harness = vi.hoisted(() => ({
  state: {
    canvasState: { kind: "ready", data: null } as unknown as CanvasState,
  },
}));

vi.mock("../../state/StudioContext", () => ({
  useStudio: () => harness.state,
}));

import { PlanPanel } from "./PlanPanel";

function renderPanel() {
  return render(<PlanPanel />);
}

describe("PlanPanel", () => {
  it("renders nothing when the canvas is empty", () => {
    renderPanel();
    expect(screen.queryByRole("region", { name: "Plan" })).toBeNull();
  });

  it("renders one row per stage, capped at six rows with an overflow row", () => {
    harness.state.canvasState = {
      kind: "ready",
      data: {
        jobs: [{ id: "J-1", name: "Deploy" }],
        steps: [{ id: "S-1", order: 5 }],
        outcomes: [],
        source: "local",
      },
    } as unknown as CanvasState;
    renderPanel();
    const panel = screen.getByRole("region", { name: "Plan" });
    const rows = panel.querySelectorAll(".plan__row");
    expect(rows).toHaveLength(6);
    const overflow = panel.querySelector(".plan__overflow");
    expect(overflow).not.toBeNull();
    expect(overflow).toHaveTextContent("+2 more");
  });

  it("renders 'Not measured' for stages without records and never a percentage", () => {
    harness.state.canvasState = {
      kind: "ready",
      data: { jobs: [{ id: "J-1" }], steps: [], outcomes: [], source: "local" },
    } as unknown as CanvasState;
    renderPanel();
    const notMeasured = screen.getAllByText("Not measured");
    expect(notMeasured.length).toBeGreaterThan(0);
    const rendered = screen.getByRole("region", { name: "Plan" }).textContent ?? "";
    expect(rendered).not.toContain("%");
  });
});
