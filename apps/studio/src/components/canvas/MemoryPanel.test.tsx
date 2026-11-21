import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { CanvasData, Observation } from "../../types";
import { MemoryPanel } from "./MemoryPanel";

const mocks = vi.hoisted(() => ({
  addObservation: vi.fn().mockResolvedValue({}),
  updateObservation: vi.fn().mockResolvedValue({}),
  deleteObservation: vi.fn().mockResolvedValue(undefined),
  clearMemory: vi.fn().mockResolvedValue(undefined),
  focusSubject: vi.fn(),
}));

let mockMemory: Observation[] = [];
let mockMemoryLoading = false;
let mockCanvas: CanvasData | null = null;

vi.mock("../../state/StudioContext", () => ({
  useStudio: () => ({
    memory: mockMemory,
    memoryLoading: mockMemoryLoading,
    canvas: mockCanvas,
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

function canvas(overrides: Partial<CanvasData> = {}): CanvasData {
  return {
    jobs: [{ id: "JOB-1", name: "Onboarding", description: "First run" }],
    steps: [],
    outcomes: [
      {
        id: "O-12",
        job_id: "JOB-1",
        statement: "service onboarding time",
        importance: 8,
        satisfaction: 3,
      },
    ],
    evidence: [],
    source: "seed",
    ...overrides,
  };
}

describe("MemoryPanel", () => {
  beforeEach(() => {
    mockMemory = [];
    mockMemoryLoading = false;
    mockCanvas = null;
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
      kind: "constraint",
      text: "We can't change pricing this quarter.",
      confirmed: true,
    });
  });

  it("clears everything only after a second confirmation", () => {
    mockMemory = [observation({})];
    render(<MemoryPanel />);

    fireEvent.click(screen.getByRole("button", { name: "Forget everything" }));
    expect(mocks.clearMemory).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Forget everything" }));
    expect(mocks.clearMemory).toHaveBeenCalledTimes(1);
  });

  it("names the record a note is about and focuses it on click", () => {
    mockCanvas = canvas();
    mockMemory = [
      observation({
        status: "confirmed",
        subject_type: "outcome",
        subject_id: "O-12",
      }),
    ];
    render(<MemoryPanel />);

    const subject = screen.getByRole("button", {
      name: "About Onboarding · O-12 · service onboarding time",
    });
    fireEvent.click(subject);
    expect(mocks.focusSubject).toHaveBeenCalledWith("outcome", "O-12");
  });

  it("says Not attached for a note with no subject", () => {
    mockCanvas = canvas();
    mockMemory = [observation({ status: "confirmed" })];
    render(<MemoryPanel />);

    expect(screen.getByText("Not attached")).toBeInTheDocument();
    expect(mocks.focusSubject).not.toHaveBeenCalled();
  });

  it("says a subject is gone instead of showing a bare id", () => {
    mockCanvas = canvas({ outcomes: [] });
    mockMemory = [
      observation({ status: "confirmed", subject_type: "outcome", subject_id: "O-99" }),
    ];
    render(<MemoryPanel />);

    expect(
      screen.getByText("About a outcome that is no longer on this canvas · O-99"),
    ).toBeInTheDocument();
    expect(mocks.focusSubject).not.toHaveBeenCalled();
  });
});
