import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { EvidenceStream } from "./EvidenceStream";

const openPanel = vi.fn();

vi.mock("../../state/StudioContext", () => ({
  useStudio: () => ({ openPanel }),
}));

describe("EvidenceStream", () => {
  it("renders an honest empty state instead of sample evidence figures", () => {
    const { container } = render(<EvidenceStream />);

    expect(screen.getByText(/no customer evidence yet/i)).toBeInTheDocument();
    expect(screen.queryByText(/Gong call/i)).not.toBeInTheDocument();
    expect(container.querySelector(".evidence-figure")).toBeNull();
  });

  it("opens Settings from the empty-state CTA", () => {
    render(<EvidenceStream />);

    fireEvent.click(screen.getByRole("button", { name: /connect a source/i }));

    expect(openPanel).toHaveBeenCalledWith("settings");
  });
});
