/**
 * The interview card: three to five structured questions, answerable in the
 * thread — and, once saved, the record of what was asked (issue #400).
 *
 * Pure presentation. It owns no store, performs no fetch, and decides nothing
 * about what an answer means — the conductor (#397) reads the answers and
 * creates the records. A live interview renders a question per kind, enforces
 * the required ones on submit, and announces the reason a submit was refused.
 * An answered one collapses into a single line that expands to the answers and
 * the records they produced, so the record of what was asked stays reviewable
 * instead of disappearing into prose.
 */

import { useState } from "react";

import { QuestionnaireField } from "../../vendor/components/assistant/questionnaire";
import {
  answeredSummaryLine,
  notSavedLine,
  recordLinks,
  type AnsweredInterview,
} from "./answered";
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
  /**
   * Present once the answers were saved: the card renders as a record of the
   * interview instead of a live form. Absent while the interview is unfinished,
   * so the live card stays mounted and answerable.
   */
  answered?: AnsweredInterview | null;
  /**
   * Called when a link to a created record is chosen. The host routes it to the
   * existing focus action; the card never opens a panel itself.
   */
  onOpenRecord?: (id: string) => void;
  /** The reason a submission did not save, kept on screen with the answers. */
  failure?: string | null;
}

function isAnswered(value: string | number | null | undefined): boolean {
  if (value === null || value === undefined) {
    return false;
  }
  return typeof value === "number" ? true : value.trim() !== "";
}

function formatAnswer(value: string | number | undefined): string {
  if (value === undefined || value === null) {
    return "—";
  }
  return typeof value === "number" ? String(value) : value.trim() || "—";
}

export function InterviewCard({
  questions,
  answers,
  onAnswer,
  onSubmit,
  busy = false,
  errors,
  answered = null,
  onOpenRecord,
  failure = null,
}: InterviewCardProps) {
  const [localErrors, setLocalErrors] = useState<Record<string, string>>({});
  const [expanded, setExpanded] = useState(false);

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

  if (answered) {
    const summary = answeredSummaryLine(answered);
    const links = recordLinks(answered.created);
    return (
      <section className="interview interview--answered" aria-label="Saved interview">
        <button
          type="button"
          className="interview__summary"
          aria-expanded={expanded}
          onClick={() => setExpanded((open) => !open)}
        >
          {summary}
        </button>
        {expanded ? (
          <div className="interview__record">
            <ol className="interview__record-list">
              {answered.questions.map((question) => (
                <li key={question.id} className="interview__record-item">
                  <p className="interview__record-prompt">{question.prompt}</p>
                  <p className="interview__record-answer">
                    {formatAnswer(answered.answers[question.id])}
                  </p>
                </li>
              ))}
            </ol>
            {links.length > 0 ? (
              <ul className="interview__record-links">
                {links.map((link) => (
                  <li key={link.id}>
                    <button
                      type="button"
                      className="interview__record-link"
                      onClick={() => onOpenRecord?.(link.id)}
                    >
                      {link.label}
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="interview__record-note">No records were created.</p>
            )}
          </div>
        ) : null}
      </section>
    );
  }

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
      {failure ? (
        <p className="interview__failure" role="status">
          {notSavedLine(failure)}
        </p>
      ) : null}
      <div className="interview__actions">
        <button type="submit" className="interview__submit" disabled={busy}>
          {busy ? "Saving…" : "Save answers"}
        </button>
      </div>
    </form>
  );
}
