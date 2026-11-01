import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { OutcomeCard } from "./OutcomeCard";

const harness = vi.hoisted(() => ({
  state: {
    ask: vi.fn(),
    deleteOutcome: vi.fn(),
    updateOutcome: vi.fn(),
    pushToast: vi.fn(),
    // The card lists the records captured against its outcome, so the canvas
    // has to be there even when this test only cares about the copy action.
    canvasState: { kind: "ready", data: { jobs: [], steps: [], outcomes: [], source: "seed" } },
  },
}));

vi.mock("../../state/StudioContext", () => ({
  useStudio: () => harness.state,
}));

const outcome = {
  id: "O-101",
  statement: "Minimize the time to sync secrets when a deployment starts.",
  importance: 9,
  satisfaction: 2,
  opportunity_score: 16,
};

describe("OutcomeCard score preview", () => {
  // The read-only card shows one decimal; the preview under "Adjust scores"
  // showed two, so 16 read as "16.0" above and "16.00" below on the same card.
  it("shows the adjusted opportunity score to one decimal", () => {
    const { container } = render(<OutcomeCard outcome={outcome} />);
    fireEvent.click(screen.getByRole("button", { name: "Adjust scores" }));

    expect(container.querySelector(".score-preview b")?.textContent).toBe("16.0");
  });
});

describe("OutcomeCard copy", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("copies the statement and confirms with a toast", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText },
      configurable: true,
    });

    render(<OutcomeCard outcome={outcome} />);
    fireEvent.click(screen.getByRole("button", { name: "Copy outcome statement" }));

    await waitFor(() => expect(writeText).toHaveBeenCalledWith(outcome.statement));
    expect(harness.state.pushToast).toHaveBeenCalledWith("success", "Copied");
  });
});
