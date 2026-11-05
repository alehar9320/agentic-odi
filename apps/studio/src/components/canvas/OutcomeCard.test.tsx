import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { OutcomeCard } from "./OutcomeCard";

const harness = vi.hoisted(() => ({
  state: {
    ask: vi.fn(),
    deleteOutcome: vi.fn(),
    updateOutcome: vi.fn(),
    pushToast: vi.fn(),
    // The card lists the records captured against its outcome, so the canvas
    // has to be there even when this test only cares about the copy action.
    canvasState: { kind: "ready", data: { jobs: [], steps: [], outcomes: [], source: "seed" } },
  },
}));

vi.mock("../../state/StudioContext", () => ({
  useStudio: () => harness.state,
}));

const outcome = {
  id: "O-101",
  statement: "Minimize the time to sync secrets when a deployment starts.",
  importance: 9,
  satisfaction: 2,
  opportunity_score: 16,
};

describe("OutcomeCard score preview", () => {
  // The read-only card shows one decimal; the preview under "Adjust scores"
  // showed two, so 16 read as "16.0" above and "16.00" below on the same card.
  it("shows the adjusted opportunity score to one decimal", () => {
    const { container } = render(<OutcomeCard outcome={outcome} />);
    fireEvent.click(screen.getByRole("button", { name: "Adjust scores" }));

    expect(container.querySelector(".score-preview b")?.textContent).toBe("16.0");
  });
});

describe("OutcomeCard copy", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows Not scored instead of a fabricated verdict for an unscored outcome", () => {
    const unscored = { ...outcome, opportunity_score: null };
    render(<OutcomeCard outcome={unscored} />);
    expect(screen.getByText("Not scored — no ratings recorded")).toBeInTheDocument();
    expect(screen.queryByText("NORMAL")).toBeNull();
    expect(screen.queryByText("Served")).toBeNull();
  });

  it("copies the statement and confirms with a toast", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText },
      configurable: true,
    });

    render(<OutcomeCard outcome={outcome} />);
    fireEvent.click(screen.getByRole("button", { name: "Copy outcome statement" }));

    await waitFor(() => expect(writeText).toHaveBeenCalledWith(outcome.statement));
    expect(harness.state.pushToast).toHaveBeenCalledWith("success", "Copied");
  });
});

describe("OutcomeCard claim check", () => {
  const asked = [
    "How often does this come up?",
    "What do you do today?",
    "What does it cost when it slips?",
  ];

  const checked = {
    ...outcome,
    claim_check: {
      asked,
      answers: ["Every week, on every new account."],
      skips: [{ question: asked[2], reason: "never measured" }],
      verified: true,
    },
  };

  it("lists what was asked, what was answered, and what was skipped", () => {
    render(<OutcomeCard outcome={checked} />);

    expect(screen.getByText(asked[0])).toBeInTheDocument();
    expect(screen.getByText("Every week, on every new account.")).toBeInTheDocument();
    expect(screen.getByText("never measured")).toBeInTheDocument();
  });

  it("counts the answers against the questions it asked", () => {
    const { container } = render(<OutcomeCard outcome={checked} />);

    expect(container.querySelector(".claim-check__head")?.textContent).toContain("1 of 3 answered");
  });

  it("marks a score with no answers recorded as unverified", () => {
    const guessed = {
      ...checked,
      claim_check: { ...checked.claim_check, answers: [], skips: [], verified: false },
    };
    const { container } = render(<OutcomeCard outcome={guessed} />);

    expect(container.querySelector(".claim-check")).toHaveClass("claim-check--unverified");
    expect(screen.getByText("Unverified")).toBeInTheDocument();
  });

  it("leaves a verified score unmarked", () => {
    const { container } = render(<OutcomeCard outcome={checked} />);

    expect(container.querySelector(".claim-check")).not.toHaveClass("claim-check--unverified");
    expect(screen.getByText("Verified")).toBeInTheDocument();
  });

  it("names a bare number when no check arrived with it", () => {
    render(<OutcomeCard outcome={outcome} />);

    expect(screen.getByText("No questions recorded behind this score")).toBeInTheDocument();
  });

  it("stays quiet when there is no number to stand behind", () => {
    const { container } = render(<OutcomeCard outcome={{ ...outcome, opportunity_score: null }} />);

    expect(container.querySelector(".claim-check")).toBeNull();
  });

  it("does not lecture the bundled sample rows", () => {
    // A by-hand notice is about the person's own numbers. The demo board is not
    // theirs, it is already badged Sample, and sample rows are excluded elsewhere.
    const { container } = render(<OutcomeCard outcome={outcome} sample />);

    expect(container.querySelector(".claim-check")).toBeNull();
  });
});
