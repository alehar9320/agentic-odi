import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { NextStep } from "../../types";
import { NextStepPrompt } from "./NextStepPrompt";

const STEP = {
  id: "ns-1",
  text: "talk to two support leads",
  created_at: "2026-10-19T10:00:00+00:00",
};

const harness = vi.hoisted(() => ({
  state: {
    openNextStep: null as NextStep | null,
    lastTurnProducedSurface: false,
    nextStepDismissed: false,
    setNextStep: vi.fn(),
    answerNextStep: vi.fn(),
    dismissNextStep: vi.fn(),
  },
}));

vi.mock("../../state/StudioContext", () => ({
  useStudio: () => harness.state,
}));

function dismissed() {
  harness.state.nextStepDismissed = true;
}

describe("NextStepPrompt", () => {
  beforeEach(() => {
    harness.state.openNextStep = null;
    harness.state.lastTurnProducedSurface = false;
    harness.state.nextStepDismissed = false;
    harness.state.setNextStep.mockReset().mockResolvedValue(undefined);
    harness.state.answerNextStep.mockReset().mockResolvedValue(undefined);
    harness.state.dismissNextStep.mockReset();
    // The visit's dismissal lives in sessionStorage; a fresh visit starts clean.
    sessionStorage.clear();
  });

  it("offers one line after a turn that put something on screen", () => {
    harness.state.lastTurnProducedSurface = true;

    render(<NextStepPrompt />);

    fireEvent.change(screen.getByLabelText(/what will you come back for/i), {
      target: { value: "talk to two support leads" },
    });
    fireEvent.click(screen.getByRole("button", { name: /remember it/i }));

    expect(harness.state.setNextStep).toHaveBeenCalledWith("talk to two support leads");
  });

  it("keeps an empty line out of the store", () => {
    harness.state.lastTurnProducedSurface = true;

    render(<NextStepPrompt />);

    fireEvent.click(screen.getByRole("button", { name: /remember it/i }));

    expect(harness.state.setNextStep).not.toHaveBeenCalled();
  });

  it("asks nothing when the last turn only talked", () => {
    const { container } = render(<NextStepPrompt />);

    expect(container).toBeEmptyDOMElement();
  });

  it("asks about the step the store is holding", () => {
    harness.state.openNextStep = STEP;

    render(<NextStepPrompt />);

    expect(screen.getByText(/talk to two support leads/)).toBeTruthy();
    expect(screen.getByRole("button", { name: /^Yes$/ })).toBeTruthy();
    expect(screen.getByRole("button", { name: /Not yet/ })).toBeTruthy();
  });

  it("answers yes with one sentence, and keeps it as evidence", () => {
    harness.state.openNextStep = STEP;

    render(<NextStepPrompt />);

    fireEvent.click(screen.getByRole("button", { name: /^Yes$/ }));
    fireEvent.change(screen.getByLabelText(/what happened/i), {
      target: { value: "Both said the queue is manual today" },
    });
    fireEvent.click(screen.getByRole("button", { name: /keep it as evidence/i }));

    expect(harness.state.answerNextStep).toHaveBeenCalledWith("ns-1", {
      done: true,
      sentence: "Both said the queue is manual today",
    });
  });

  it("writes nothing for a not-yet, and offers the two answers that do", () => {
    harness.state.openNextStep = STEP;

    render(<NextStepPrompt />);

    fireEvent.click(screen.getByRole("button", { name: /Not yet/ }));

    expect(screen.getByRole("button", { name: /Keep asking/ })).toBeTruthy();
    expect(screen.getByRole("button", { name: /Later/ })).toBeTruthy();
    expect(screen.getByRole("button", { name: /Drop it/ })).toBeTruthy();
    expect(harness.state.answerNextStep).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: /Keep asking/ }));

    // Keep asking is the honest no-op: the step stays open and the question
    // simply waits for the next visit.
    expect(harness.state.answerNextStep).not.toHaveBeenCalled();
    expect(harness.state.dismissNextStep).toHaveBeenCalled();
  });

  it("moves the date for a step postponed, without recording an answer", () => {
    harness.state.openNextStep = STEP;

    render(<NextStepPrompt />);

    fireEvent.click(screen.getByRole("button", { name: /Not yet/ }));
    fireEvent.click(screen.getByRole("button", { name: /Later/ }));
    fireEvent.change(screen.getByLabelText(/ask again on/i), {
      target: { value: "2026-12-01" },
    });
    fireEvent.click(screen.getByRole("button", { name: /set the date/i }));

    const [, answer] = harness.state.answerNextStep.mock.calls[0] as [string, Record<string, string>];
    expect(answer.action).toBe("reschedule");
    // The store refuses a reminder with no zone, so the studio names the zone
    // this browser is standing in.
    expect(new Date(answer.dueAt).getTime()).toBe(new Date("2026-12-01T00:00:00").getTime());
  });

  it("stops asking when the person drops the step", () => {
    harness.state.openNextStep = STEP;

    render(<NextStepPrompt />);

    fireEvent.click(screen.getByRole("button", { name: /Not yet/ }));
    fireEvent.click(screen.getByRole("button", { name: /Drop it/ }));

    expect(harness.state.answerNextStep).toHaveBeenCalledWith("ns-1", { action: "drop" });
  });

  it("hides for the visit that put the question away, and asks again in the next", () => {
    harness.state.openNextStep = STEP;
    harness.state.dismissNextStep.mockImplementation(dismissed);

    const first = render(<NextStepPrompt />);
    fireEvent.click(first.getByRole("button", { name: /Don.t ask again this visit/i }));
    first.rerender(<NextStepPrompt />);

    expect(first.container).toBeEmptyDOMElement();

    sessionStorage.clear();
    harness.state.nextStepDismissed = false;
    const second = render(<NextStepPrompt />);

    expect(second.getByText(/talk to two support leads/)).toBeTruthy();
  });
});
