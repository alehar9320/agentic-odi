import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { StudioContextValue } from "../state/StudioContext";
import type { CanvasData, Claim } from "../types";
import { ClaimText } from "./parts";

vi.mock("../state/StudioContext", () => ({
  useStudio: vi.fn(),
}));

import { useStudio } from "../state/StudioContext";

const focusEvidence = vi.fn();
const closePanel = vi.fn();

function canvas(overrides: Partial<CanvasData> = {}): CanvasData {
  return {
    jobs: [],
    steps: [],
    outcomes: [],
    evidence: [{ id: "E-1", name: "Call with Acme", source_name: "Gong" }],
    source: "local",
    ...overrides,
  };
}

function stub(overrides: Partial<StudioContextValue> = {}) {
  vi.mocked(useStudio).mockReturnValue({
    canvas: canvas(),
    focusEvidence,
    closePanel,
    ...overrides,
  } as unknown as StudioContextValue);
}

const cited: Claim = {
  index: 0,
  text: "Three accounts stalled.",
  status: "cited",
  evidence: [{ id: "E-1", name: "Call with Acme", source_name: "Gong" }],
  reason: null,
};

const hypothesis: Claim = {
  index: 1,
  text: "Nobody said why.",
  status: "hypothesis",
  evidence: [],
  reason: null,
};

const uncited: Claim = { index: 2, text: "The invite step is confusing.", status: "uncited", evidence: [], reason: null };

beforeEach(() => {
  vi.mocked(useStudio).mockReset();
  focusEvidence.mockReset();
  closePanel.mockReset();
});

describe("ClaimText", () => {
  it("puts a chip naming the source and record after its sentence", () => {
    stub();
    render(
      <ClaimText
        content="Three accounts stalled. [[ev:E-1]] Nobody said why. [[hypothesis]]"
        claims={[cited, hypothesis]}
      />,
    );

    const chip = screen.getByRole("button", { name: /Gong · Call with Acme/ });
    expect(chip).toHaveTextContent("Gong · Call with Acme");
    expect(screen.getByText("Hypothesis")).toBeInTheDocument();
    expect(screen.queryByText(/\[\[/)).toBeNull();
  });

  it("opens the record a chip names", () => {
    stub();
    render(<ClaimText content="Three accounts stalled. [[ev:E-1]]" claims={[cited]} />);

    fireEvent.click(screen.getByRole("button", { name: /Call with Acme/ }));

    expect(focusEvidence).toHaveBeenCalledWith("E-1");
  });

  it("marks an uncited sentence without hiding it", () => {
    stub();
    render(<ClaimText content="The invite step is confusing." claims={[uncited]} />);

    expect(screen.getByText("The invite step is confusing.")).toBeInTheDocument();
    expect(screen.getByText("Uncited claim.")).toBeInTheDocument();
  });

  it("keeps the snapshot label when the record is gone but does not link it", () => {
    stub({ canvas: canvas({ evidence: [] }) });
    render(<ClaimText content="Three accounts stalled. [[ev:E-1]]" claims={[cited]} />);

    expect(screen.queryByRole("button")).toBeNull();
    expect(screen.getByText("Gong · Call with Acme")).toBeInTheDocument();
    expect(screen.getByText("This record is no longer in the studio.")).toBeInTheDocument();
  });

  it("labels a seeded demo chip as a sample and excludes it from the count", () => {
    stub({ canvas: canvas({ source: "seed" }) });
    render(<ClaimText content="Three accounts stalled. [[ev:E-1]]" claims={[cited]} />);

    expect(screen.getByText("Sample")).toBeInTheDocument();
    expect(screen.queryByText("This reply has no citations")).toBeNull();
  });

  it("says once when a reply has no citations at all", () => {
    stub();
    render(<ClaimText content="The invite step is confusing." claims={[uncited]} />);

    expect(screen.getByText("This reply has no citations")).toBeInTheDocument();
  });

  it("returns focus to the lens when a chip is dismissed with Escape", () => {
    stub();
    render(<ClaimText content="Three accounts stalled. [[ev:E-1]]" claims={[cited]} />);

    fireEvent.keyDown(screen.getByRole("button", { name: /Call with Acme/ }), { key: "Escape" });

    expect(closePanel).toHaveBeenCalled();
  });
});
