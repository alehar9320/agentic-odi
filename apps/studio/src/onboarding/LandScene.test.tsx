import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SAMPLE_COMPARISON_IDS, SAMPLE_MISSING_EVIDENCE, SAMPLE_OUTCOME_ID } from "../lib/sampleLoop";
import { LandScene } from "./LandScene";

describe("LandScene", () => {
  it("plots the sample outcome and highlights exactly that id", () => {
    const { container } = render(<LandScene />);

    expect(screen.getByRole("img", { name: "Opportunity map" })).toBeInTheDocument();

    const highlighted = container.querySelectorAll(".matrix-node--highlighted");
    expect(highlighted).toHaveLength(1);
    expect(highlighted[0]).toHaveAttribute("data-highlighted", "true");
    expect(highlighted[0]).toHaveAccessibleName(new RegExp(`^${SAMPLE_OUTCOME_ID},`));
  });

  it("marks the scene as sample and names what it does not prove", () => {
    render(<LandScene />);

    expect(screen.getByText("Sample")).toBeInTheDocument();
    expect(screen.getByText("What the sample does not prove")).toBeInTheDocument();
    for (const item of SAMPLE_MISSING_EVIDENCE) {
      expect(screen.getByText(item)).toBeInTheDocument();
    }
  });

  it("keeps the comparisons on the plot without highlighting them", () => {
    const { container } = render(<LandScene />);

    for (const comparison of SAMPLE_COMPARISON_IDS) {
      const node = container.querySelector(`.matrix-node[aria-label^="${comparison},"]`);
      expect(node).not.toBeNull();
      expect(node).not.toHaveAttribute("data-highlighted");
    }
  });
});
