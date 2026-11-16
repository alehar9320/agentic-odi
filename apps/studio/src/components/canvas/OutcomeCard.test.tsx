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

  it("shows a partly verified indicator with the answered and skipped basis", () => {
    const { container } = render(<OutcomeCard outcome={checked} />);

    expect(container.querySelector(".claim-check__head")?.textContent).toContain("1 of 3 answered");
    expect(container.querySelector(".claim-check__head")?.textContent).toContain("1 skipped");
    expect(container.querySelector(".claim-check--partial")).not.toBeNull();
    expect(screen.getByText("Partly verified")).toBeInTheDocument();
  });

  it("marks a score with no answers recorded as a hypothesis", () => {
    const guessed = {
      ...checked,
      claim_check: { ...checked.claim_check, answers: [], skips: [], verified: false },
    };
    const { container } = render(<OutcomeCard outcome={guessed} />);

    expect(container.querySelector(".claim-check")).toHaveClass("claim-check--hypothesis");
    expect(screen.getByText("Hypothesis")).toBeInTheDocument();
  });

  it("reads a fully answered, verified score as verified", () => {
    const fullyAnswered = {
      ...outcome,
      claim_check: {
        asked: asked.slice(0, 2),
        answers: ["Every week.", "A script."],
        skips: [],
        verified: true,
      },
    };
    const { container } = render(<OutcomeCard outcome={fullyAnswered} />);

    expect(container.querySelector(".claim-check")).toHaveClass("claim-check--verified");
    expect(screen.getByText("Verified")).toBeInTheDocument();
  });

  it("names a bare number as a hypothesis when no check arrived with it", () => {
    render(<OutcomeCard outcome={outcome} />);

    expect(screen.getByText("nothing backs this yet")).toBeInTheDocument();
    expect(screen.getByText("Hypothesis")).toBeInTheDocument();
  });

  it("reveals the linked quotes from the indicator itself, not a second control", () => {
    // A quote captured against this outcome, with its way back to the source.
    harness.state.canvasState = {
      kind: "ready",
      data: {
        jobs: [],
        steps: [],
        outcomes: [],
        evidence: [
          {
            id: "E-1",
            outcome_id: "O-101",
            content: "We sync secrets by hand every deploy.",
            source_name: "Linear",
          },
        ],
        source: "local",
      },
    } as unknown as typeof harness.state.canvasState;

    try {
      const { container } = render(<OutcomeCard outcome={checked} />);

      expect(container.querySelector(".card__evidence")).toBeNull();

      const indicator = screen.getByRole("button", { name: /Partly verified/i });
      expect(indicator).toHaveAttribute("aria-expanded", "false");
      fireEvent.click(indicator);
      expect(indicator).toHaveAttribute("aria-expanded", "true");

      // One reveal path: the same evidence panel the "Evidence" button drives.
      expect(screen.getByText(/We sync secrets by hand every deploy./)).toBeInTheDocument();
      expect(screen.getByText(/Via Linear/)).toBeInTheDocument();
    } finally {
      harness.state.canvasState = {
        kind: "ready",
        data: { jobs: [], steps: [], outcomes: [], source: "seed" },
      };
    }
  });

  it("stays quiet when there is no number to stand behind", () => {
    const { container } = render(<OutcomeCard outcome={{ ...outcome, opportunity_score: null }} />);

    expect(container.querySelector(".claim-check")).toBeNull();
  });

  it("does not lecture the bundled sample rows", () => {
    // A backing notice is about the person's own numbers. The demo board is not
    // theirs, it is already badged Sample, and sample rows are excluded elsewhere.
    const { container } = render(<OutcomeCard outcome={outcome} sample />);

    expect(container.querySelector(".claim-check")).toBeNull();
    expect(container.querySelector(".badge--button")).toBeNull();
  });
});

describe("OutcomeCard advances link", () => {
  it("names the objective an outcome advances, with the field", () => {
    const linked = {
      ...outcome,
      trace: [{ field: "method", key: "abc123", text: "Cut release time in half" }],
    };
    render(<OutcomeCard outcome={linked} />);
    expect(screen.getByText(/Advances Cut release time in half \(method\)/i)).toBeInTheDocument();
  });

  it("joins several links with a separator", () => {
    const linked = {
      ...outcome,
      trace: [
        { field: "method", key: "abc123", text: "Cut release time in half" },
        { field: "measure", key: "def456", text: "Release time" },
      ],
    };
    render(<OutcomeCard outcome={linked} />);
    expect(screen.getByText(/Cut release time in half \(method\) · Release time \(measure\)/i)).toBeInTheDocument();
  });

  it("says plainly that an unlinked outcome advances nothing yet", () => {
    render(<OutcomeCard outcome={outcome} />);
    expect(screen.getByText("Advances nothing yet")).toBeInTheDocument();
  });

  it("never invents an objective from a guessed id", () => {
    // The link text is recorded at filing time. A reworded vision leaves the
    // frozen text behind as drift evidence rather than updating the card.
    const drifted = {
      ...outcome,
      trace: [{ field: "method", key: "old-key", text: "Old objective wording" }],
    };
    render(<OutcomeCard outcome={drifted} />);
    expect(screen.getByText(/Old objective wording \(method\)/i)).toBeInTheDocument();
    expect(screen.queryByText(/new objective/i)).toBeNull();
  });
});
