import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { OutcomeCard } from "./OutcomeCard";

vi.mock("../../state/StudioContext", () => ({
  useStudio: () => ({
    ask: vi.fn(),
    deleteOutcome: vi.fn(),
    pushToast: vi.fn(),
    updateOutcome: vi.fn(),
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
