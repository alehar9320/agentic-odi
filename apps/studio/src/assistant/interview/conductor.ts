/**
 * The interview conductor (issue #397).
 *
 * The interview card (#396) is presentation: it renders questions and reports
 * answers. This module is the machine behind it — a pure reducer that walks an
 * interview from `idle` to `done`, and a thin shell that turns the answers into
 * records through the actions `StudioContext` already exposes. No new MCP tool,
 * no `TOOL_SPECS` change: the conductor only calls `createJob`, `addOutcome`,
 * and `addEvidence`.
 *
 * `reduce` owns every transition and performs no I/O, so the whole state graph
 * is testable without a renderer or a network. `createConductor` is the impure
 * edge: it runs the plan in order and reports what the store said back.
 */

import type { Question } from "../../components/interview/types";

export type AnswerValue = string | number;
export type Answers = Record<string, AnswerValue>;

export type InterviewStatus =
  | "idle"
  | "asking"
  | "collecting"
  | "submitting"
  | "done"
  | "failed"
  | "abandoned";

/** The ids the submit path produced, in the order it produced them. */
export interface CreatedRecords {
  jobId: string | null;
  outcomeIds: string[];
  evidenceCount: number;
}

/**
 * Where a submit stopped. A failure keeps whatever the earlier steps created,
 * so a partial write is reported rather than rolled back into a lie.
 */
export interface SubmitFailure {
  step: "job" | "outcome" | "evidence";
  /** The index within its kind; `0` for the single job step. */
  index: number;
  message: string;
}

export interface InterviewState {
  status: InterviewStatus;
  questions: Question[];
  answers: Answers;
  /** The question the person is answering. */
  index: number;
  /** The id of the required question that blocked a submit, if any. */
  invalid: string | null;
  created: CreatedRecords;
  failure: SubmitFailure | null;
}

export type InterviewEvent =
  | { type: "ask"; questions: Question[] }
  | { type: "begin" }
  | { type: "answer"; questionId: string; value: AnswerValue }
  | { type: "next" }
  | { type: "submit" }
  | { type: "submitted"; created: CreatedRecords }
  | { type: "failed"; failure: SubmitFailure; created: CreatedRecords }
  | { type: "abandon" };

function emptyCreated(): CreatedRecords {
  return { jobId: null, outcomeIds: [], evidenceCount: 0 };
}

export function initialState(): InterviewState {
  return {
    status: "idle",
    questions: [],
    answers: {},
    index: 0,
    invalid: null,
    created: emptyCreated(),
    failure: null,
  };
}

function isAnswered(value: AnswerValue | undefined): boolean {
  if (value === undefined || value === null) {
    return false;
  }
  return typeof value === "number" ? true : value.trim() !== "";
}

/** The first required question with no answer, or null when the card is complete. */
export function firstMissing(questions: Question[], answers: Answers): string | null {
  for (const question of questions) {
    if (question.required && !isAnswered(answers[question.id])) {
      return question.id;
    }
  }
  return null;
}

/**
 * One transition. Pure: the same state and event always give the same result,
 * and nothing here awaits, fetches, or writes.
 */
export function reduce(state: InterviewState, event: InterviewEvent): InterviewState {
  switch (event.type) {
    case "ask":
      return { ...initialState(), status: "asking", questions: event.questions };

    case "begin":
      return state.status === "asking" ? { ...state, status: "collecting", index: 0 } : state;

    case "answer": {
      if (state.status !== "collecting") {
        return state;
      }
      const answers = { ...state.answers, [event.questionId]: event.value };
      return {
        ...state,
        answers,
        // Answering the blocked question clears its refusal immediately, so a
        // person is never told a field is empty while looking at what they typed.
        invalid: state.invalid === event.questionId ? null : state.invalid,
      };
    }

    case "next": {
      if (state.status !== "collecting") {
        return state;
      }
      const last = Math.max(0, state.questions.length - 1);
      return { ...state, index: Math.min(state.index + 1, last) };
    }

    case "submit": {
      // A second submit while a submit is in flight is a no-op: the store must
      // never be asked to create the same record twice.
      if (state.status !== "collecting") {
        return state;
      }
      const missing = firstMissing(state.questions, state.answers);
      if (missing) {
        return { ...state, invalid: missing };
      }
      return { ...state, status: "submitting", invalid: null };
    }

    case "submitted":
      return state.status === "submitting"
        ? { ...state, status: "done", created: event.created, failure: null }
        : state;

    case "failed":
      return state.status === "submitting"
        ? { ...state, status: "failed", created: event.created, failure: event.failure }
        : state;

    case "abandon":
      return { ...state, status: "abandoned" };

    default:
      return state;
  }
}

// ---------------------------------------------------------------------------
// The interview script, and the plan it produces
// ---------------------------------------------------------------------------

/**
 * The five questions an interview asks, in the order ODI asks them: the job,
 * one desired outcome in the ODI form, how important and how satisfied, and
 * what the person actually heard.
 */
export const INTERVIEW_QUESTIONS: Question[] = [
  {
    id: "job",
    kind: "statement",
    prompt: "In one sentence, what job is this market trying to get done?",
    required: true,
  },
  {
    id: "outcome",
    kind: "text",
    prompt: "What is the customer trying to get done?",
    help: "Use the form: Minimize the time it takes to …",
    required: true,
  },
  {
    id: "importance",
    kind: "scale",
    prompt: "How important is this outcome to the customer?",
    min: 1,
    max: 10,
    required: true,
  },
  {
    id: "satisfaction",
    kind: "scale",
    prompt: "How satisfied are they with it today?",
    min: 1,
    max: 10,
    required: true,
  },
  {
    id: "evidence",
    kind: "text",
    prompt: "What did you hear that supports this?",
    help: "One quote or one sentence is enough.",
    required: false,
  },
];

/** What the conductor asks the store to create, in submission order. */
export interface InterviewPlan {
  job: { name: string; description?: string };
  outcomes: { statement: string; importance: number; satisfaction: number }[];
  evidence: {
    name: string;
    content: string;
    sourceName: string;
    itemType?: string;
    /** Which outcome this evidence supports, by index; omitted means the job. */
    outcomeIndex?: number;
  }[];
}

function text(value: AnswerValue | undefined): string {
  return typeof value === "string" ? value.trim() : "";
}

function scale(value: AnswerValue | undefined, fallback: number): number {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string" && value.trim() !== "" && Number.isFinite(Number(value))) {
    return Number(value);
  }
  return fallback;
}

/**
 * Read a plan from the script's answers. Pure, so the mapping from what was
 * said to what is written is one function a test can pin. An unanswered
 * optional question produces nothing rather than an empty record.
 */
export function planFromAnswers(answers: Answers): InterviewPlan {
  const statement = text(answers.outcome);
  const heard = text(answers.evidence);
  const outcomes = statement
    ? [
        {
          statement,
          importance: scale(answers.importance, 5),
          satisfaction: scale(answers.satisfaction, 5),
        },
      ]
    : [];
  return {
    job: { name: text(answers.job) || "Untitled job" },
    outcomes,
    evidence: heard
      ? [{ name: "Interview note", content: heard, sourceName: "interview", outcomeIndex: 0 }]
      : [],
  };
}

// ---------------------------------------------------------------------------
// The impure shell
// ---------------------------------------------------------------------------

/**
 * The three store actions the conductor is allowed to call. Kept as a port so
 * the machine never imports the store and a test drives it with a plain object.
 */
export interface InterviewPorts {
  createJob(payload: { name: string; description?: string }): Promise<string | null>;
  addOutcome(payload: {
    job_id: string;
    statement: string;
    importance: number;
    satisfaction: number;
  }): Promise<string | null>;
  addEvidence(payload: {
    job_id?: string;
    outcome_id?: string;
    name: string;
    content: string;
    source_name: string;
    item_type?: string;
  }): Promise<void>;
}

export interface Conductor {
  getState(): InterviewState;
  send(event: InterviewEvent): void;
  subscribe(listener: (state: InterviewState) => void): () => void;
}

function messageOf(error: unknown): string {
  return error instanceof Error && error.message ? error.message : "The write did not complete.";
}

export function createConductor(options: {
  ports: InterviewPorts;
  /** Built from the answers at submit time, or fixed for a single script. */
  plan: (answers: Answers) => InterviewPlan;
  onState?: (state: InterviewState) => void;
}): Conductor {
  let state = initialState();
  const listeners = new Set<(state: InterviewState) => void>();

  const emit = () => {
    options.onState?.(state);
    for (const listener of listeners) {
      listener(state);
    }
  };

  /**
   * Create the records in order: the job, then each outcome, then each evidence
   * item. A failure stops the run and reports where it stopped, leaving every
   * record already created in place.
   */
  async function runPlan(plan: InterviewPlan): Promise<void> {
    const created = emptyCreated();
    const fail = (failure: SubmitFailure) => {
      state = reduce(state, { type: "failed", failure, created });
      emit();
    };

    try {
      created.jobId = await options.ports.createJob(plan.job);
    } catch (error) {
      fail({ step: "job", index: 0, message: messageOf(error) });
      return;
    }

    for (const [index, outcome] of plan.outcomes.entries()) {
      try {
        const outcomeId = await options.ports.addOutcome({
          job_id: created.jobId ?? "",
          statement: outcome.statement,
          importance: outcome.importance,
          satisfaction: outcome.satisfaction,
        });
        if (outcomeId) {
          created.outcomeIds.push(outcomeId);
        }
      } catch (error) {
        fail({ step: "outcome", index, message: messageOf(error) });
        return;
      }
    }

    for (const [index, item] of plan.evidence.entries()) {
      const outcomeId =
        item.outcomeIndex === undefined ? undefined : created.outcomeIds[item.outcomeIndex];
      try {
        await options.ports.addEvidence({
          job_id: created.jobId ?? undefined,
          outcome_id: outcomeId,
          name: item.name,
          content: item.content,
          source_name: item.sourceName,
          item_type: item.itemType,
        });
        created.evidenceCount += 1;
      } catch (error) {
        fail({ step: "evidence", index, message: messageOf(error) });
        return;
      }
    }

    state = reduce(state, { type: "submitted", created });
    emit();
  }

  return {
    getState: () => state,
    send: (event) => {
      const next = reduce(state, event);
      const starting = state.status !== "submitting" && next.status === "submitting";
      state = next;
      emit();
      if (starting) {
        // The plan is read once, from the answers the submit was validated
        // against, so a late keystroke cannot change what is being written.
        void runPlan(options.plan(next.answers));
      }
    },
    subscribe: (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
  };
}
