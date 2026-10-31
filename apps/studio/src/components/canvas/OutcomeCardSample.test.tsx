import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { OutcomeCard } from "./OutcomeCard";

vi.mock("../../api/studioApi", () => ({
  fetchOutcomeHistory: vi.fn().mockResolvedValue([]),
  fetchOutcomeInterval: vi.fn().mockResolvedValue({ outcome_id: "", band: null }),
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
  id: "O-SEED",
  statement: "Minimize the time to onboard when a customer signs up.",
  importance: 9,
  satisfaction: 2,
  opportunity_score: 16,
};

describe("OutcomeCard sample data", () => {
  it("marks a seeded outcome and explains what the chip means", () => {
    render(<OutcomeCard outcome={outcome} sample />);

    const chip = screen.getByText("Sample");
    expect(chip).toHaveAttribute(
      "title",
      "This is bundled sample data, not yours.",
    );
  });

  it("does not mark the user's own outcome", () => {
    render(<OutcomeCard outcome={outcome} />);

    expect(screen.queryByText("Sample")).toBeNull();
  });
});
