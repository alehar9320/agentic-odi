import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { StudioBrief } from "../../types";
import { DataSection } from "./sections/DataSection";

const brief: StudioBrief = {
  product_name: "Acme",
  target_user: "analysts",
  job_statement: "decide what to build next",
  core_problem: "no shared evidence",
  v2mom: { vision: "Every bet traces to evidence." },
};

function renderSection(overrides: Partial<Parameters<typeof DataSection>[0]> = {}) {
  const props = {
    brief: null as StudioBrief | null,
    openSetup: vi.fn(),
    displayName: "Ada",
    setDisplayName: vi.fn(),
    closeSetup: vi.fn(),
    clearChat: vi.fn(),
    refreshCanvas: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  };
  return { ...render(<DataSection {...props} />), props };
}

describe("DataSection", () => {
  it("says the context is not set and offers to set it", () => {
    const { props } = renderSection({ brief: null });

    expect(screen.getByText(/not set yet/i)).toBeInTheDocument();
    const button = screen.getByRole("button", { name: /set up context/i });
    fireEvent.click(button);
    expect(props.openSetup).toHaveBeenCalled();
  });

  it("states the job statement and vision once they exist", () => {
    renderSection({ brief });

    expect(screen.getByText(/Acme — decide what to build next/)).toBeInTheDocument();
    expect(screen.getByText(/Every bet traces to evidence/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /edit context/i })).toBeInTheDocument();
  });

  it("edits the display name through its own control", () => {
    const { props } = renderSection();

    const input = screen.getByLabelText(/your name/i) as HTMLInputElement;
    expect(input.value).toBe("Ada");

    fireEvent.change(input, { target: { value: "Grace" } });
    expect(props.setDisplayName).toHaveBeenCalledWith("Grace");
  });

  it("starts a new conversation and syncs the canvas", () => {
    const { props } = renderSection();

    fireEvent.click(screen.getByRole("button", { name: /start a new conversation/i }));
    expect(props.closeSetup).toHaveBeenCalled();
    expect(props.clearChat).toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: /sync canvas/i }));
    expect(props.refreshCanvas).toHaveBeenCalled();
  });
});
