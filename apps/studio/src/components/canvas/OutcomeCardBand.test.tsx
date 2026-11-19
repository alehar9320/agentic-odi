import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchOutcomeInterval } from "../../api/studioApi";
import { OutcomeCard } from "./OutcomeCard";

vi.mock("../../api/studioApi", () => ({
  fetchOutcomeHistory: vi.fn().mockResolvedValue([]),
  fetchOutcomeInterval: vi.fn(),
  fetchOutcomeAlternatives: vi.fn().mockResolvedValue([]),
  fetchExistingSolution: vi.fn().mockResolvedValue("no_link_at_all"),
  fetchAlternativeLinks: vi.fn().mockResolvedValue([]),
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

const interval = vi.mocked(fetchOutcomeInterval);

describe("OutcomeCard band provenance", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("says plainly when a score carries no band", async () => {
    interval.mockResolvedValue({ outcome_id: "O-101", band: null });

    render(<OutcomeCard outcome={outcome} detail />);

    await waitFor(() =>
      expect(screen.getByTestId("outcome-band-provenance")).toHaveTextContent("no band"),
    );
  });

  it("names the sample, confidence and seed behind a stored band", async () => {
    interval.mockResolvedValue({
      outcome_id: "O-101",
      band: {
        low: 14.0,
        high: 18.0,
        n: 40,
        confidence_level: 0.95,
        seed: 7,
        method: "survey",
        computed_at: "2026-01-01T00:00:00+00:00",
        stale: false,
      },
    });

    render(<OutcomeCard outcome={outcome} detail />);

    const line = await screen.findByTestId("outcome-band-provenance");
    expect(line).toHaveTextContent("n=40");
    expect(line).toHaveTextContent("95%");
    expect(line).toHaveTextContent("seed 7");
    expect(line).not.toHaveTextContent("stale");
  });

  it("marks a band stale when a later snapshot moved the score", async () => {
    interval.mockResolvedValue({
      outcome_id: "O-101",
      band: {
        low: 14.0,
        high: 18.0,
        n: 40,
        confidence_level: 0.95,
        seed: null,
        method: "survey",
        computed_at: "2026-01-01T00:00:00+00:00",
        stale: true,
      },
    });

    render(<OutcomeCard outcome={outcome} detail />);

    const line = await screen.findByTestId("outcome-band-provenance");
    expect(line).toHaveTextContent("stale");
    expect(line).toHaveTextContent("seed unrecorded");
  });

  it("stays quiet when the band cannot be read", async () => {
    interval.mockRejectedValue(new Error("unreachable"));

    render(<OutcomeCard outcome={outcome} detail />);

    await waitFor(() => expect(interval).toHaveBeenCalled());
    expect(screen.queryByTestId("outcome-band-provenance")).toBeNull();
  });
});
