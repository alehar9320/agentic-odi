/**
 * The interview card: three to five structured questions, answerable in the
 * thread.
 *
 * Pure presentation. It owns no store, performs no fetch, and decides nothing
 * about what an answer means — the conductor (#397) reads the answers and
 * creates the records. The card only renders a question per kind, enforces the
 * required ones on submit, and announces the reason a submit was refused.
 */

import { useState } from "react";

import { QuestionnaireField } from "../../vendor/components/assistant/questionnaire";
import type { Question } from "./types";

/** The one sentence a refused required answer shows, per the copy standard. */
export const REQUIRED_ANSWER_MESSAGE = "An answer is needed before this can be saved.";

const STATEMENT_HINT = "Use the form: Minimize the time it takes to …";

export interface InterviewCardProps {
  questions: Question[];
  answers: Record<string, string | number>;
  onAnswer: (questionId: string, value: string | number) => void;
  onSubmit: () => void;
  /** True while the answers are being turned into records; disables submit. */
  busy?: boolean;
  /** Errors from the submit path, keyed by question id, merged with local ones. */
  errors?: Record<string, string>;
}

function isAnswered(value: string | number | null | undefined): boolean {
  if (value === null || value === undefined) {
    return false;
  }
  return typeof value === "number" ? true : value.trim() !== "";
}

export function InterviewCard({
  questions,
  answers,
  onAnswer,
  onSubmit,
  busy = false,
  errors,
}: InterviewCardProps) {
  const [localErrors, setLocalErrors] = useState<Record<string, string>>({});

  const errorFor = (id: string): string | null => localErrors[id] ?? errors?.[id] ?? null;

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const missing: Record<string, string> = {};
    for (const question of questions) {
      if (question.required && !isAnswered(answers[question.id])) {
        missing[question.id] = REQUIRED_ANSWER_MESSAGE;
      }
    }
    setLocalErrors(missing);
    if (Object.keys(missing).length === 0) {
      onSubmit();
    }
  };

  // Clearing the local error as soon as an answer arrives means a person is not
  // told a field is empty while they are looking at the text they just typed.
  const handleAnswer = (id: string, value: string | number) => {
    if (localErrors[id]) {
      setLocalErrors((previous) => {
        const next = { ...previous };
        delete next[id];
        return next;
      });
    }
    onAnswer(id, value);
  };

  return (
    <form className="interview" aria-label="Interview" onSubmit={handleSubmit}>
      {questions.map((question) => (
        <QuestionnaireField
          key={question.id}
          id={question.id}
          kind={question.kind}
          prompt={question.prompt}
          help={question.help ?? (question.kind === "statement" ? STATEMENT_HINT : undefined)}
          min={question.min}
          max={question.max}
          required={question.required}
          value={answers[question.id] ?? null}
          error={errorFor(question.id)}
          onChange={(value) => handleAnswer(question.id, value)}
        />
      ))}
      <div className="interview__actions">
        <button type="submit" className="interview__submit" disabled={busy}>
          {busy ? "Saving…" : "Save answers"}
        </button>
      </div>
    </form>
  );
}
