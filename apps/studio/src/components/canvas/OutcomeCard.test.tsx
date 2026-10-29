import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { OutcomeCard } from "./OutcomeCard";

const harness = vi.hoisted(() => ({
  state: {
    ask: vi.fn(),
    deleteOutcome: vi.fn(),
    updateOutcome: vi.fn(),
    fetchOutcomeEvidence: vi.fn(),
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

describe("OutcomeCard copy", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    harness.state.fetchOutcomeEvidence.mockReset();
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

  it("shows the evidence count read from the store, not a stored counter", async () => {
    harness.state.fetchOutcomeEvidence.mockResolvedValue([
      { id: "ev-1", source_name: "Ana onboarding", content: "Setup takes forever." },
      { id: "ev-2", source_name: "Bo onboarding", content: "It is slow to start." },
    ]);

    render(<OutcomeCard outcome={outcome} />);
    fireEvent.click(screen.getByRole("button", { name: "Evidence" }));

    await waitFor(() => expect(harness.state.fetchOutcomeEvidence).toHaveBeenCalledWith("O-101"));
    expect(await screen.findByText("2 sources behind this number")).toBeInTheDocument();
    expect(screen.getByText("Setup takes forever.")).toBeInTheDocument();
  });

  it("says the outcome has no linked transcript when the store is empty", async () => {
    harness.state.fetchOutcomeEvidence.mockResolvedValue([]);

    render(<OutcomeCard outcome={outcome} />);
    fireEvent.click(screen.getByRole("button", { name: "Evidence" }));

    expect(
      await screen.findByText("No transcript is linked to this outcome yet."),
    ).toBeInTheDocument();
  });
});
