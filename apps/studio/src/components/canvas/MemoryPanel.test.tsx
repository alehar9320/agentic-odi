import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Observation } from "../../types";
import { MemoryPanel } from "./MemoryPanel";

const mocks = vi.hoisted(() => ({
  updateObservation: vi.fn().mockResolvedValue({}),
  deleteObservation: vi.fn().mockResolvedValue(undefined),
  clearMemory: vi.fn().mockResolvedValue(undefined),
}));

let mockMemory: Observation[] = [];

vi.mock("../../state/StudioContext", () => ({
  useStudio: () => ({
    memory: mockMemory,
    memoryLoading: false,
    ...mocks,
  }),
}));

function observation(overrides: Partial<Observation>): Observation {
  return {
    id: "o-1",
    kind: "career",
    text: "Accountable for activation.",
    data: {},
    status: "confirmed",
    confidence: 0.9,
    source_turn: 1,
    created_at: "2026-10-22T10:00:00+00:00",
    updated_at: "2026-10-22T10:00:00+00:00",
    ...overrides,
  };
}

describe("MemoryPanel", () => {
  beforeEach(() => {
    mockMemory = [];
    vi.clearAllMocks();
  });

  it("explains the empty state", () => {
    render(<MemoryPanel />);
    expect(screen.getByText("Nothing yet.")).toBeInTheDocument();
  });

  it("asks about a guess and confirms it", () => {
    mockMemory = [observation({ status: "suggested", text: "You own activation." })];
    render(<MemoryPanel />);

    expect(screen.getByText("Did I get this right?")).toBeInTheDocument();
    expect(screen.getByText("Your role")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Yes, that's right" }));
    expect(mocks.updateObservation).toHaveBeenCalledWith("o-1", { status: "confirmed" });
  });

  it("dismisses a wrong guess", () => {
    mockMemory = [observation({ status: "suggested" })];
    render(<MemoryPanel />);

    fireEvent.click(screen.getByRole("button", { name: "That's not it" }));
    expect(mocks.updateObservation).toHaveBeenCalledWith("o-1", { status: "dismissed" });
  });

  it("forgets a confirmed observation", () => {
    mockMemory = [observation({ status: "confirmed", text: "Prefers short updates." })];
    render(<MemoryPanel />);

    expect(screen.getByText("What I'm working from")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Forget Prefers short updates." }));
    expect(mocks.deleteObservation).toHaveBeenCalledWith("o-1");
  });

  it("clears everything only after a second confirmation", () => {
    mockMemory = [observation({})];
    render(<MemoryPanel />);

    fireEvent.click(screen.getByRole("button", { name: "Forget everything" }));
    expect(mocks.clearMemory).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Forget everything" }));
    expect(mocks.clearMemory).toHaveBeenCalledTimes(1);
  });
});
