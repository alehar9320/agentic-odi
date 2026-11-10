import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { opportunityScore } from "../lib/odi";
import { sampleLoop } from "../lib/sampleLoop";
import { HearScene, ScoreScene } from "./steps";

const loop = sampleLoop();

/** The sample outcome's statement, which both scenes show. */
const outcomeStatement = loop.outcome.statement ?? "";

describe("scene one — a quote becomes a scored outcome", () => {
  it("shows the quote, its source line, and the Sample badge", () => {
    render(<HearScene />);

    expect(screen.getByText("Sample")).toBeInTheDocument();
    expect(
      screen.getByText(
        "I keep a spreadsheet of config keys because I can't tell which ones are live.",
        { exact: false },
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("one onboarding call, sample")).toBeInTheDocument();
  });

  it("offers three readings and names the workaround and the solution as wrong", () => {
    render(<HearScene />);

    const answers = screen.getAllByRole("button");
    expect(answers).toHaveLength(3);

    // The workaround is named for what it is, not just marked wrong.
    fireEvent.click(screen.getByRole("button", { name: /Keep a spreadsheet/ }));
    expect(screen.getByRole("status")).toHaveTextContent("current workaround");

    // The solution in disguise is named too.
    fireEvent.click(screen.getByRole("button", { name: /Stop using config keys/ }));
    expect(screen.getByRole("status")).toHaveTextContent("solution in disguise");
  });

  it("reveals the evidence record and the outcome linked to it once the job is chosen", () => {
    render(<HearScene />);

    // Nothing is revealed before the right pick.
    expect(screen.queryByText("Evidence record")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Know which config is live/ }));

    expect(screen.getByText("Evidence record")).toBeInTheDocument();
    expect(screen.getByText("Outcome record — linked to the evidence")).toBeInTheDocument();
    // Both records exist, and the outcome names the evidence it came from.
    expect(
      screen.getByText(`Evidence ${loop.quote.id} → outcome ${loop.outcome.id}`),
    ).toBeInTheDocument();
    expect(screen.getByText(outcomeStatement)).toBeInTheDocument();
  });

  it("chooses an answer with the 1 / 2 / 3 keys", () => {
    render(<HearScene />);

    fireEvent.keyDown(window, { key: "2" });
    expect(screen.getByRole("status")).toHaveTextContent("current workaround");

    fireEvent.keyDown(window, { key: "1" });
    expect(screen.getByText("Evidence record")).toBeInTheDocument();
  });
});

describe("scene two — two numbers become a scored outcome", () => {
  it("shows the arithmetic before the number, and pins it to 15", () => {
    render(<ScoreScene />);

    expect(
      screen.getByText("Importance 9, plus the 6-point gap, is 15."),
    ).toBeInTheDocument();
    expect(screen.getByText("15.0")).toBeInTheDocument();
    expect(screen.getByText("🔥 Underserved (Opp: 15.0)")).toBeInTheDocument();
  });

  it("stores importance and satisfaction and recomputes with the real formula", () => {
    render(<ScoreScene />);

    const importance = screen.getByLabelText(/Importance/, { selector: "input" });
    const satisfaction = screen.getByLabelText(/Satisfaction/, { selector: "input" });
    expect(importance).toHaveValue("9");
    expect(satisfaction).toHaveValue("3");

    fireEvent.change(satisfaction, { target: { value: "9" } });

    // 9 + max(9 - 9, 0) = 9, and the label flips at the threshold.
    expect(
      screen.getByText("Importance 9, plus no gap, is 9."),
    ).toBeInTheDocument();
    expect(screen.getByText("9.0")).toBeInTheDocument();
    expect(screen.getByText("✓ Served (Opp: 9.0)")).toBeInTheDocument();
  });

  it("keeps the displayed number equal to the shared formula for any pair", () => {
    render(<ScoreScene />);

    const importance = screen.getByLabelText(/Importance/, { selector: "input" });
    const satisfaction = screen.getByLabelText(/Satisfaction/, { selector: "input" });

    fireEvent.change(importance, { target: { value: "8" } });
    fireEvent.change(satisfaction, { target: { value: "2" } });

    // 8 + (8 - 2) = 14 — the same number the studio's own function returns.
    expect(opportunityScore(8, 2)).toBe(14);
    expect(screen.getByText("14.0")).toBeInTheDocument();
  });
});
