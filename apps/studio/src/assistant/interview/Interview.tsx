/**
 * The interview in the thread (issues #397, #400).
 *
 * This is the wiring point: it renders the interview card (#396), reports the
 * person's answers to the conductor, and hands the conductor's result back to
 * the caller. The choice of owner is deliberate — the conductor is the machine
 * that turns answers into records, and `ChatStage`/`StudioRuntime` already
 * delegate record creation to `StudioContext`, so the interview is a host
 * component that composes the card and the conductor rather than a new
 * orchestration path inside either file.
 *
 * Once the conductor reports the records it created, the host hands them back
 * to the card as `answered`, so a finished interview collapses into the record
 * of itself (#400) while an unfinished one stays live and answerable.
 */

import { useEffect, useRef, useState } from "react";

import { InterviewCard, REQUIRED_ANSWER_MESSAGE } from "../../components/interview/InterviewCard";
import type { AnsweredInterview } from "../../components/interview/answered";
import type { Question } from "../../components/interview/types";
import {
  createConductor,
  INTERVIEW_QUESTIONS,
  planFromAnswers,
  type Answers,
  type CreatedRecords,
  type InterviewPlan,
  type InterviewPorts,
  type InterviewState,
} from "./conductor";

export interface InterviewProps {
  /** The store actions the conductor may call; stable for one interview. */
  ports: InterviewPorts;
  questions?: Question[];
  plan?: (answers: Answers) => InterviewPlan;
  /** Called once every record is created. */
  onComplete?: (created: CreatedRecords) => void;
  /** Called when a write stopped part-way, naming the step that failed. */
  onFailure?: (state: InterviewState) => void;
  /**
   * Open a record the answers created, through the host's existing focus
   * action. The card offers one link per created outcome.
   */
  onOpenRecord?: (id: string) => void;
}

export function Interview({
  ports,
  questions = INTERVIEW_QUESTIONS,
  plan = planFromAnswers,
  onComplete,
  onFailure,
  onOpenRecord,
}: InterviewProps) {
  const [state, setState] = useState<InterviewState>(() =>
    createConductor({ ports, plan }).getState(),
  );
  // One conductor per mounted interview. `setState` is stable, so capturing it
  // in the lazy initialiser keeps the machine's notifications flowing to this
  // component without a second effect to re-subscribe.
  const [conductor] = useState(() => createConductor({ ports, plan, onState: setState }));
  // The callbacks live in a ref so a re-render with new closures does not
  // re-create the conductor or fire a stale completion.
  const notify = useRef({ onComplete, onFailure });
  useEffect(() => {
    notify.current = { onComplete, onFailure };
  });

  useEffect(() => {
    conductor.send({ type: "ask", questions });
    conductor.send({ type: "begin" });
  }, [conductor, questions]);

  useEffect(() => {
    if (state.status === "done") {
      notify.current.onComplete?.(state.created);
    } else if (state.status === "failed") {
      notify.current.onFailure?.(state);
    }
  }, [state]);

  const errors = state.invalid === null ? undefined : { [state.invalid]: REQUIRED_ANSWER_MESSAGE };

  // The record of a finished interview, built from the answers the submit was
  // validated against and the records the store confirmed. A failed submit
  // leaves the card live, with the reason on screen and the answers intact.
  const answered: AnsweredInterview | null =
    state.status === "done"
      ? {
          questions: questions.map((question) => ({
            id: question.id,
            prompt: question.prompt,
          })),
          answers: state.answers,
          created: {
            outcomeIds: state.created.outcomeIds,
            evidenceCount: state.created.evidenceCount,
          },
        }
      : null;

  const failure = state.status === "failed" && state.failure ? state.failure.message : null;

  return (
    <InterviewCard
      questions={questions}
      answers={state.answers}
      onAnswer={(questionId, value) => conductor.send({ type: "answer", questionId, value })}
      onSubmit={() => conductor.send({ type: "submit" })}
      busy={state.status === "submitting"}
      errors={errors}
      answered={answered}
      onOpenRecord={onOpenRecord}
      failure={failure}
    />
  );
}
