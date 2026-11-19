import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { expectAccessible } from "../../test/axe";
import { InterviewCard, REQUIRED_ANSWER_MESSAGE } from "./InterviewCard";
import { isQuestion, type Question } from "./types";

const questions: Question[] = [
  {
    id: "q-statement",
    kind: "statement",
    prompt: "In one sentence, what job is this market trying to get done?",
    required: true,
  },
  { id: "q-text", kind: "text", prompt: "What did you hear that surprised you?", help: "A few words is enough.", required: false },
  { id: "q-scale", kind: "scale", prompt: "How important is this outcome?", min: 1, max: 10, required: true },
];

function renderCard(overrides: Partial<React.ComponentProps<typeof InterviewCard>> = {}) {
  const props = {
    questions,
    answers: {},
    onAnswer: vi.fn(),
    onSubmit: vi.fn(),
    ...overrides,
  };
  return { ...render(<InterviewCard {...props} />), props };
}

describe("InterviewCard", () => {
  it("renders the right control and accessible name per kind", () => {
    renderCard();
    expect(
      screen.getByRole("textbox", { name: /what job is this market trying to get done/i }),
    ).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: /what did you hear/i })).toBeInTheDocument();
    expect(screen.getByRole("slider", { name: /how important is this outcome/i })).toBeInTheDocument();
  });

  it("marks a required question and leaves an optional one unmarked", () => {
    renderCard();
    expect(screen.getByRole("textbox", { name: /what job is this market/i })).toHaveAttribute(
      "aria-required",
      "true",
    );
    expect(screen.getByRole("textbox", { name: /what did you hear/i })).not.toHaveAttribute(
      "aria-required",
    );
  });

  it("shows the current scale value beside the range", () => {
    renderCard({ answers: { "q-scale": 7 } });
    expect(screen.getByRole("slider", { name: /how important/i })).toHaveValue("7");
    expect(screen.getByText("7")).toBeInTheDocument();
  });

  it("reports an answer as it is typed", () => {
    const onAnswer = vi.fn();
    renderCard({ onAnswer });
    fireEvent.change(screen.getByRole("textbox", { name: /what did you hear/i }), {
      target: { value: "They retype the same note" },
    });
    expect(onAnswer).toHaveBeenCalledWith("q-text", "They retype the same note");
  });

  it("refuses a submit while a required answer is empty and says why", () => {
    const onSubmit = vi.fn();
    renderCard({ onSubmit });
    fireEvent.click(screen.getByRole("button", { name: /save answers/i }));
    expect(onSubmit).not.toHaveBeenCalled();
    expect(screen.getAllByText(REQUIRED_ANSWER_MESSAGE).length).toBeGreaterThan(0);
    expect(screen.getByRole("textbox", { name: /what job is this market/i })).toHaveAttribute(
      "aria-invalid",
      "true",
    );
  });

  it("submits once every required answer is present", () => {
    const onSubmit = vi.fn();
    renderCard({ answers: { "q-statement": "Hand off a deployment", "q-scale": 8 }, onSubmit });
    fireEvent.click(screen.getByRole("button", { name: /save answers/i }));
    expect(onSubmit).toHaveBeenCalledTimes(1);
  });

  it("clears a required error as soon as the answer arrives", () => {
    renderCard();
    fireEvent.click(screen.getByRole("button", { name: /save answers/i }));
    expect(screen.getAllByText(REQUIRED_ANSWER_MESSAGE).length).toBe(2);
    fireEvent.change(screen.getByRole("textbox", { name: /what job is this market/i }), {
      target: { value: "Hand off a deployment" },
    });
    expect(screen.getAllByText(REQUIRED_ANSWER_MESSAGE).length).toBe(1);
  });

  it("surfaces an error handed back from the submit path", () => {
    renderCard({ answers: { "q-statement": "x", "q-scale": 5 }, errors: { "q-text": "Not saved — try again." } });
    expect(screen.getByText("Not saved — try again.")).toBeInTheDocument();
  });

  it("disables submit while the answers are being saved", () => {
    renderCard({ busy: true });
    expect(screen.getByRole("button", { name: /saving/i })).toBeDisabled();
  });

  it("passes the axe sweep with one error showing", async () => {
    const { container } = render(
      <main>
        <h1>Interview</h1>
        <InterviewCard
          questions={questions}
          answers={{}}
          onAnswer={vi.fn()}
          onSubmit={vi.fn()}
          errors={{ "q-text": "Not saved — try again." }}
        />
      </main>,
    );
    await expectAccessible(container);
  });
});

const answeredInterview = {
  questions: [
    { id: "job", prompt: "In one sentence, what job is this market trying to get done?" },
    { id: "outcome", prompt: "What is the customer trying to get done?" },
    { id: "importance", prompt: "How important is this outcome to the customer?" },
  ],
  answers: {
    job: "Turn interview notes into one opportunity",
    outcome: "Minimize the time it takes to turn notes into a scored outcome",
    importance: 9,
  },
  created: { outcomeIds: ["outcome-1", "outcome-2"], evidenceCount: 1 },
};

describe("InterviewCard answered record", () => {
  it("reads as one line with the counts from the records, not the answers", () => {
    renderCard({ answered: answeredInterview });

    expect(screen.getByRole("button", { name: /Answered · 3 of 3 · 2 outcomes, 1 evidence/ })).toBeInTheDocument();
  });

  it("says 0 outcomes when the answers produced no records", () => {
    renderCard({
      answered: {
        questions: answeredInterview.questions,
        answers: answeredInterview.answers,
        created: { outcomeIds: [], evidenceCount: 0 },
      },
    });

    expect(screen.getByRole("button", { name: /0 outcomes, 0 evidence/ })).toBeInTheDocument();
  });

  it("is collapsed until expanded, then shows the answers", () => {
    renderCard({ answered: answeredInterview });

    expect(screen.queryByText("What is the customer trying to get done?")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Answered/ }));
    expect(screen.getByText("What is the customer trying to get done?")).toBeInTheDocument();
    expect(
      screen.getByText("Minimize the time it takes to turn notes into a scored outcome"),
    ).toBeInTheDocument();
  });

  it("links each created record and reports the focus action once", () => {
    const onOpenRecord = vi.fn();
    renderCard({ answered: answeredInterview, onOpenRecord });

    fireEvent.click(screen.getByRole("button", { name: /Answered/ }));
    fireEvent.click(screen.getByRole("button", { name: "Outcome 2" }));

    expect(onOpenRecord).toHaveBeenCalledTimes(1);
    expect(onOpenRecord).toHaveBeenCalledWith("outcome-2");
  });

  it("offers no link when nothing was created", () => {
    renderCard({
      answered: {
        questions: answeredInterview.questions,
        answers: answeredInterview.answers,
        created: { outcomeIds: [], evidenceCount: 0 },
      },
    });

    fireEvent.click(screen.getByRole("button", { name: /Answered/ }));
    expect(screen.getByText("No records were created.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Outcome/ })).not.toBeInTheDocument();
  });

  it("keeps the live form answerable after a failed submit", () => {
    renderCard({
      answers: { job: "x", outcome: "y", importance: 5 },
      failure: "The store refused the write.",
    });

    expect(screen.getByRole("button", { name: /save answers/i })).toBeInTheDocument();
    expect(screen.getByText("Not saved — The store refused the write.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Answered/ })).not.toBeInTheDocument();
  });

  it("passes the axe sweep on the expanded record", async () => {
    const { container } = render(
      <main>
        <h1>Interview</h1>
        <InterviewCard
          questions={questions}
          answers={answeredInterview.answers}
          onAnswer={vi.fn()}
          onSubmit={vi.fn()}
          answered={answeredInterview}
        />
      </main>,
    );
    fireEvent.click(screen.getByRole("button", { name: /Answered/ }));
    await expectAccessible(container);
  });
});

describe("isQuestion", () => {
  it("accepts all three well-formed kinds", () => {
    expect(isQuestion({ id: "a", kind: "statement", prompt: "p", required: true })).toBe(true);
    expect(isQuestion({ id: "b", kind: "text", prompt: "p", required: false })).toBe(true);
    expect(isQuestion({ id: "c", kind: "scale", prompt: "p", min: 1, max: 10, required: true })).toBe(
      true,
    );
  });

  it("refuses a malformed question", () => {
    expect(isQuestion(null)).toBe(false);
    expect(isQuestion({ kind: "text", prompt: "p", required: false })).toBe(false);
    expect(isQuestion({ id: "a", kind: "slider", prompt: "p", required: false })).toBe(false);
    expect(isQuestion({ id: "a", kind: "text", prompt: "", required: false })).toBe(false);
    expect(isQuestion({ id: "a", kind: "text", prompt: "p" })).toBe(false);
  });

  it("requires a scale to carry a defined span", () => {
    expect(isQuestion({ id: "a", kind: "scale", prompt: "p", min: 5, max: 5, required: true })).toBe(
      false,
    );
    expect(isQuestion({ id: "a", kind: "scale", prompt: "p", required: true })).toBe(false);
  });
});
