import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Observation } from "../../types";
import { MemoryPanel } from "./MemoryPanel";

const mocks = vi.hoisted(() => ({
  addObservation: vi.fn().mockResolvedValue({}),
  updateObservation: vi.fn().mockResolvedValue({}),
  deleteObservation: vi.fn().mockResolvedValue(undefined),
  clearMemory: vi.fn().mockResolvedValue(undefined),
}));

let mockMemory: Observation[] = [];
let mockMemoryLoading = false;
let mockMessages: { id: string; role: string; content: string }[] = [];

vi.mock("../../state/StudioContext", () => ({
  useStudio: () => ({
    memory: mockMemory,
    memoryLoading: mockMemoryLoading,
    messages: mockMessages,
    ...mocks,
  }),
}));

function observation(overrides: Partial<Observation>): Observation {
  return {
    id: "o-1",
    category: "career",
    text: "Accountable for activation.",
    data: {},
    status: "confirmed",
    confidence: 0.9,
    created_at: "2026-10-22T10:00:00+00:00",
    updated_at: "2026-10-22T10:00:00+00:00",
    ...overrides,
  };
}

describe("MemoryPanel", () => {
  beforeEach(() => {
    mockMemory = [];
    mockMemoryLoading = false;
    mockMessages = [];
    vi.clearAllMocks();
  });

  it("shows skeleton lines while memory loads", () => {
    mockMemoryLoading = true;
    const { container } = render(<MemoryPanel />);

    expect(screen.queryByText(/Reading back what I've learned/)).toBeNull();
    expect(container.querySelectorAll(".skeleton").length).toBeGreaterThanOrEqual(3);
  });

  it("explains the empty state", () => {
    render(<MemoryPanel />);
    expect(screen.getByText("Nothing yet.")).toBeInTheDocument();
  });

  it("asks about a guess and confirms it", () => {
    mockMemory = [observation({ status: "proposed", text: "You own activation." })];
    render(<MemoryPanel />);

    expect(screen.getByText("Did I get this right?")).toBeInTheDocument();
    expect(screen.getByText("Your role")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Yes, that's right" }));
    expect(mocks.updateObservation).toHaveBeenCalledWith("o-1", { status: "confirmed" });
  });

  it("dismisses a wrong guess", () => {
    mockMemory = [observation({ status: "proposed" })];
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

  it("edits a note", () => {
    mockMemory = [observation({ status: "confirmed", text: "Owns activation." })];
    render(<MemoryPanel />);

    fireEvent.click(screen.getByRole("button", { name: "Edit" }));
    fireEvent.change(screen.getByLabelText("Edit this note"), {
      target: { value: "Owns activation and retention." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(mocks.updateObservation).toHaveBeenCalledWith("o-1", {
      text: "Owns activation and retention.",
    });
  });

  it("adds a note the PM types", () => {
    render(<MemoryPanel />);

    fireEvent.click(screen.getByRole("button", { name: "Add something" }));
    fireEvent.change(screen.getByLabelText("What kind of note?"), {
      target: { value: "constraint" },
    });
    fireEvent.change(screen.getByLabelText("What should I remember?"), {
      target: { value: "We can't change pricing this quarter." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Add" }));

    expect(mocks.addObservation).toHaveBeenCalledWith({
      category: "constraint",
      text: "We can't change pricing this quarter.",
      confirmed: true,
    });
  });

  it("shows the line a guess came from, so it can be judged", () => {
    mockMessages = [{ id: "m-1", role: "user", content: "We always plan on Mondays." }];
    mockMemory = [
      observation({
        status: "proposed",
        category: "preference",
        text: "Plans on Mondays.",
        source_message_id: "m-1",
      }),
    ];
    render(<MemoryPanel />);

    expect(screen.getByText("You said: We always plan on Mondays.")).toBeInTheDocument();
    expect(screen.getByText("How you work")).toBeInTheDocument();
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
