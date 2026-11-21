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
import {
  createDraftWriter,
  latestDraft,
  type DraftStore,
  type DraftWriter,
} from "./persistence";

/** The draft store a host hands the interview so a reload resumes it (#402). */
export interface InterviewDraftOptions {
  store: DraftStore;
  /** The job the draft belongs to; a draft for another job is never restored. */
  jobId: string;
  /** The interview's identity in the store. Defaults to the job id. */
  interviewId?: string;
  /** The debounce window; a test narrows it. */
  debounceMs?: number;
  /** The clock for `updatedAt`; a test pins it. */
  now?: () => string;
}

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
  /**
   * Persist and restore the draft. Absent when the host keeps no draft, in
   * which case the interview behaves exactly as before (#402 is opt-in).
   */
  draft?: InterviewDraftOptions;
}

export function Interview({
  ports,
  questions = INTERVIEW_QUESTIONS,
  plan = planFromAnswers,
  onComplete,
  onFailure,
  onOpenRecord,
  draft,
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

  // One writer for the mounted interview. A ref, not state: the writer is not
  // rendered, and creating it in the initialiser would need the store open at
  // first paint.
  const writer = useRef<DraftWriter | null>(null);
  // The restore effect depends on the draft's identity, not on the options
  // object: a host that rebuilds that object each render must not re-read the
  // store and reopen an already-answered question.
  const draftStore = draft?.store ?? null;
  const draftJobId = draft?.jobId ?? null;
  const draftInterviewId = draft?.interviewId ?? null;
  const draftDebounceMs = draft?.debounceMs;
  const draftNow = draft?.now;

  useEffect(() => {
    conductor.send({ type: "ask", questions });
    conductor.send({ type: "begin" });
  }, [conductor, questions]);

  // Restore the most recent draft for this job before the person types, then
  // keep writing on every transition. A draft for another job is ignored.
  useEffect(() => {
    if (!draftStore || !draftJobId) {
      return;
    }
    let cancelled = false;
    const active = createDraftWriter({
      store: draftStore,
      interviewId: draftInterviewId ?? draftJobId,
      jobId: draftJobId,
      ...(draftDebounceMs === undefined ? {} : { debounceMs: draftDebounceMs }),
      ...(draftNow === undefined ? {} : { now: draftNow }),
    });
    writer.current = active;

    void (async () => {
      const stored = await latestDraft(draftStore, draftJobId);
      if (!cancelled && stored) {
        conductor.send({ type: "restore", answers: stored.answers, index: stored.index });
      }
    })();

    return () => {
      cancelled = true;
      writer.current = null;
      void active.flush();
    };
  }, [conductor, draftStore, draftJobId, draftInterviewId, draftDebounceMs, draftNow]);

  // Every transition writes the draft; a terminal state deletes it. Debounced,
  // so a burst of answers inside the window is one write.
  useEffect(() => {
    writer.current?.write(state);
  }, [state]);

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
