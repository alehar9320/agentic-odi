import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import indexHtml from "../../index.html?raw";
import { OpportunityLandscape } from "./canvas/OpportunityLandscape";
import { OutcomeCard } from "./canvas/OutcomeCard";
import { Toasts } from "./Toasts";

const mockOutcome = {
  id: "O-101",
  job_id: "JOB-1",
  statement: "Minimize time required to sync environment secrets",
  importance: 9.2,
  satisfaction: 2.1,
  opportunity_score: 16.3,
  evidence: "Gong transcript #42",
};

const mockCanvasData = {
  jobs: [{ id: "JOB-1", name: "Deploy Service" }],
  steps: [{ id: "STEP-1", name: "Configure secrets", order: 1 }],
  outcomes: [mockOutcome],
  source: "seed" as const,
};

vi.mock("../state/StudioContext", () => ({
  useStudio: () => ({
    toasts: [{ id: "toast-1", kind: "info", message: "Outcome recorded" }],
    dismissToast: vi.fn(),
    canvas: mockCanvasData,
    canvasLoading: false,
    ask: vi.fn(),
    deleteOutcome: vi.fn(),
    updateOutcome: vi.fn(),
  }),
}));

describe("Mobile UX", () => {
  it("keeps the viewport safe-area aware so notches do not cover the chrome", () => {
    expect(indexHtml).toContain("viewport-fit=cover");
  });

  it("gives the toast dismiss button a 44px touch target", () => {
    render(<Toasts />);

    const dismiss = screen.getByRole("button", { name: "Dismiss notification" });
    expect(dismiss.style.minHeight).toBe("44px");
    expect(dismiss.style.minWidth).toBe("44px");
  });

  it("gives the underserved filter a 44px touch target", () => {
    render(<OpportunityLandscape />);

    const filter = screen.getByText(/Show Underserved Only/i);
    expect(filter.style.minHeight).toBe("44px");
  });

  it("names the outcome in its accessible label so a screen reader says what it is", () => {
    render(<OutcomeCard outcome={mockOutcome} />);

    expect(
      screen.getByRole("article", { name: /Minimize time required to sync environment secrets/i }),
    ).toBeInTheDocument();
  });
});
