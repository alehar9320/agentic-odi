import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { Hero } from "./Hero";
import type { NextStep } from "../../types";

const harness = vi.hoisted(() => ({
  state: {
    displayName: "Ada",
    canvas: undefined,
    llmHealth: { healthy: true, message: "ok" },
    brief: null,
    openSetup: vi.fn(),
    openNextStep: null as NextStep | null,
    nextStepDismissed: false as boolean,
  },
  tour: { enabled: false, openTour: vi.fn() },
}));

vi.mock("../../state/StudioContext", () => ({
  useStudio: () => harness.state,
}));

vi.mock("../../onboarding/context", () => ({
  useOnboarding: () => harness.tour,
}));

function headline() {
  return screen.getByRole("heading", { level: 1 }).textContent ?? "";
}

describe("Hero", () => {
  beforeEach(() => {
    vi.useFakeTimers({ now: new Date("2026-10-22T10:00:00+00:00") });
    harness.state.openNextStep = null;
    harness.state.nextStepDismissed = false;
    harness.state.brief = null;
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("greets the promise the last visit left open", () => {
    harness.state.openNextStep = {
      id: "ns-1",
      text: "talk to two support leads",
      created_at: "2026-10-19T10:00:00+00:00",
    };

    render(<Hero />);

    expect(headline()).toBe(
      "Last time you said you would talk to two support leads (3d ago). Did it happen?",
    );
  });

  it("greets today like any other day when nothing is outstanding", () => {
    render(<Hero />);

    expect(headline()).toBe("What do you want to win?");
  });

  it("greets today when the store has a step it cannot name", () => {
    // A row written by an older build, or blanked by hand: the studio must not
    // ask "Last time you said you would  (0d ago)".
    harness.state.openNextStep = { id: "ns-1", text: "  ", created_at: "2026-10-22T09:59:00+00:00" };

    render(<Hero />);

    expect(headline()).toBe("What do you want to win?");
  });

  it("does not ask again about a promise already answered", () => {
    harness.state.openNextStep = {
      id: "ns-1",
      text: "talk to two support leads",
      created_at: "2026-10-19T10:00:00+00:00",
      resolved_at: "2026-10-20T10:00:00+00:00",
      resolution: "Both said the queue is manual today",
    };

    render(<Hero />);

    expect(headline()).toBe("What do you want to win?");
  });

  it("asks nothing on either screen once the person said not to ask this visit", () => {
    // The ✕ in the dock promises "quiet for this visit". A reload keeps the
    // thread empty and the promise open, so the greeting is the second place
    // that ask could come back — and it must not.
    harness.state.openNextStep = {
      id: "ns-1",
      text: "talk to two support leads",
      created_at: "2026-10-19T10:00:00+00:00",
    };
    harness.state.nextStepDismissed = true;

    render(<Hero />);

    expect(headline()).toBe("What do you want to win?");
  });
});
