import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { CanvasData } from "../../types";
import type { StudioContextValue } from "../../state/StudioContext";

vi.mock("../../state/StudioContext", () => ({
  useStudio: vi.fn(),
}));

import { useStudio } from "../../state/StudioContext";
import { ContextChip } from "./ContextChip";

const canvas: CanvasData = {
  jobs: [{ id: "JOB-7", name: "Faster onboarding" }],
  steps: [{ id: "S-3", job_id: "JOB-7", name: "Instrument the welcome email" }],
  outcomes: [{ id: "O-101", job_id: "JOB-7", statement: "New teams reach first value in a day" }],
  evidence: [{ id: "E-9", name: "Renewal call with Northwind" }],
  source: "mcp",
};

function renderChip(overrides: Record<string, unknown> = {}) {
  vi.mocked(useStudio).mockReturnValue(
    {
      focusedSubject: null,
      canvas,
      revealSubject: vi.fn(),
      ...overrides,
    } as unknown as StudioContextValue,
  );
  return render(<ContextChip />);
}

describe("ContextChip", () => {
  it("renders nothing while no record is focused", () => {
    const { container } = renderChip({ focusedSubject: null });

    expect(container).toBeEmptyDOMElement();
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("names the job the studio is pointed at", () => {
    renderChip({ focusedSubject: { kind: "job", id: "JOB-7" } });

    const chip = screen.getByRole("button", { name: /agent context: job faster onboarding/i });
    expect(chip).toHaveTextContent("Faster onboarding");
  });

  it("names the step the studio is pointed at", () => {
    renderChip({ focusedSubject: { kind: "step", id: "S-3" } });

    expect(screen.getByRole("button", { name: /welcome email/i })).toHaveTextContent(
      "Instrument the welcome email",
    );
  });

  it("names the outcome by its statement", () => {
    renderChip({ focusedSubject: { kind: "outcome", id: "O-101" } });

    expect(screen.getByRole("button", { name: /first value in a day/i })).toHaveTextContent(
      "New teams reach first value in a day",
    );
  });

  it("names the evidence record the studio is pointed at", () => {
    renderChip({ focusedSubject: { kind: "evidence", id: "E-9" } });

    expect(screen.getByRole("button", { name: /northwind/i })).toHaveTextContent(
      "Renewal call with Northwind",
    );
  });

  it("says which record it holds when the board has not loaded it", () => {
    renderChip({ focusedSubject: { kind: "job", id: "JOB-9" }, canvas: null });

    const chip = screen.getByRole("button", { name: /agent context: job job-9/i });
    expect(chip).toHaveTextContent("JOB-9");
    expect(chip).not.toHaveTextContent("Faster onboarding");
  });

  it("opens the lens that holds the record when the chip is clicked", () => {
    const revealSubject = vi.fn();
    renderChip({ focusedSubject: { kind: "outcome", id: "O-101" }, revealSubject });

    fireEvent.click(screen.getByRole("button", { name: /first value in a day/i }));

    expect(revealSubject).toHaveBeenCalledWith("outcome", "O-101");
  });

  it("explains to a screen reader that the chip names the agent's context", () => {
    renderChip({ focusedSubject: { kind: "job", id: "JOB-7" } });

    expect(screen.getByRole("button", { name: /faster onboarding/i })).toHaveAccessibleDescription(
      /opens the record the agent is pointed at/i,
    );
  });
});
