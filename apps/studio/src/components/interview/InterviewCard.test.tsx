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
