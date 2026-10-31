import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { OutcomeCard } from "./OutcomeCard";

vi.mock("../../api/studioApi", () => ({
  fetchOutcomeHistory: vi.fn().mockResolvedValue([]),
  fetchOutcomeInterval: vi.fn().mockResolvedValue({ outcome_id: "", band: null }),
  fetchOutcomeAlternatives: vi.fn().mockResolvedValue([]),
  fetchExistingSolution: vi.fn().mockResolvedValue("no_link_at_all"),
  fetchAlternativeLinks: vi.fn().mockResolvedValue([]),
}));

const harness = vi.hoisted(() => ({
  state: {
    ask: vi.fn(),
    deleteOutcome: vi.fn(),
    updateOutcome: vi.fn(),
    pushToast: vi.fn(),
    // The card lists the records captured against its outcome, so the canvas
    // has to be there even when this test only cares about the copy action.
    canvasState: { kind: "ready", data: { jobs: [], steps: [], outcomes: [], source: "seed" } },
    settings: { mcp_url: "http://localhost:8000/mcp" },
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
