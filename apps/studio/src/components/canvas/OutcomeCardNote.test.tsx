import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchOutcomeHistory } from "../../api/studioApi";
import { OutcomeCard } from "./OutcomeCard";

vi.mock("../../api/studioApi", () => ({
  fetchOutcomeHistory: vi.fn(),
}));

vi.mock("../../state/StudioContext", () => ({
  useStudio: () => ({
    ask: vi.fn(),
    canvasState: { data: { evidence: [] } },
    deleteOutcome: vi.fn(),
    pushToast: vi.fn(),
    updateOutcome: vi.fn(),
    settings: { mcp_url: "http://localhost:8000/mcp" },
  }),
}));

const outcome = {
  id: "O-101",
  statement: "Minimize the time to sync secrets when a deployment starts.",
  importance: 9,
  satisfaction: 2,
  opportunity_score: 16,
};

const history = vi.mocked(fetchOutcomeHistory);

describe("OutcomeCard note", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("shows the reason from the most recent accepted change", async () => {
    history.mockResolvedValue([
      {
        id: "S-1",
        outcome_id: "O-101",
        at: "2026-01-01T00:00:00+00:00",
        satisfaction: 2,
        note: "first pass",
      },
      {
        id: "S-2",
        outcome_id: "O-101",
        at: "2026-01-02T00:00:00+00:00",
        satisfaction: 3,
        note: "after the review",
      },
    ]);

    render(<OutcomeCard outcome={outcome} detail />);

    await waitFor(() =>
      expect(screen.getByTestId("outcome-note")).toHaveTextContent("after the review"),
    );
    expect(screen.getByTestId("outcome-note")).not.toHaveTextContent("first pass");
  });

  it("omits the note line when no reason was recorded", async () => {
    history.mockResolvedValue([
      { id: "S-1", outcome_id: "O-101", at: "2026-01-01T00:00:00+00:00", satisfaction: 2 },
    ]);

    render(<OutcomeCard outcome={outcome} detail />);

    await waitFor(() => expect(history).toHaveBeenCalled());
    expect(screen.queryByTestId("outcome-note")).toBeNull();
  });

  it("stays quiet when history cannot be read", async () => {
    history.mockRejectedValue(new Error("unreachable"));

    render(<OutcomeCard outcome={outcome} detail />);

    await waitFor(() => expect(history).toHaveBeenCalled());
    expect(screen.queryByTestId("outcome-note")).toBeNull();
  });

  it("does not read history for a list card", async () => {
    history.mockResolvedValue([
      {
        id: "S-1",
        outcome_id: "O-101",
        at: "2026-01-01T00:00:00+00:00",
        satisfaction: 2,
        note: "should not load",
      },
    ]);

    render(<OutcomeCard outcome={outcome} />);

    await Promise.resolve();
    expect(history).not.toHaveBeenCalled();
    expect(screen.queryByTestId("outcome-note")).toBeNull();
  });
});
