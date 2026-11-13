import type { InterviewConductorState, InterviewPersistence, InterviewQuestion } from "./persistence";

export interface InterviewConductor {
  readonly state: InterviewConductorState;
  readonly currentQuestion: InterviewQuestion | null;
  readonly isComplete: boolean;
  readonly progress: { current: number; total: number };

  answer(value: string | number): Promise<void>;
  next(): Promise<void>;
  previous(): Promise<void>;
  submit(): Promise<void>;
  cancel(): Promise<void>;
  subscribe(listener: () => void): () => void;
}

const DEFAULT_QUESTIONS: readonly InterviewQuestion[] = [
  { id: "role", text: "What role does the person hold?", kind: "text" },
  { id: "context", text: "Describe the situation or context.", kind: "text" },
  { id: "struggle", text: "What are they trying to do that existing solutions don't solve?", kind: "text" },
  { id: "workaround", text: "How do they handle it today?", kind: "text" },
  { id: "importance", text: "How important is solving this? (1-10)", kind: "number", min: 1, max: 10 },
  { id: "satisfaction", text: "How satisfied are they with current workarounds? (1-10)", kind: "number", min: 1, max: 10 },
];

export function createInterviewConductor(
  jobId: string,
  persistence: InterviewPersistence,
  initialState?: Partial<InterviewConductorState>,
): InterviewConductor {
  const state: InterviewConductorState = {
    id: crypto.randomUUID(),
    jobId,
    state: "idle",
    answers: {},
    index: 0,
    questions: DEFAULT_QUESTIONS,
    ...initialState,
  };

  const listeners = new Set<() => void>();

  function notify() {
    for (const listener of listeners) {
      listener();
    }
  }

  async function persist() {
    if (state.state === "collecting" || state.state === "asking") {
      await persistence.saveDraftImmediately(state);
    } else if (state.state === "submitted" || state.state === "cancelled") {
      await persistence.deleteDraft(jobId);
    }
  }

  return {
    get state() {
      return { ...state };
    },
    get currentQuestion() {
      if (state.index >= 0 && state.index < state.questions.length) {
        return state.questions[state.index];
      }
      return null;
    },
    get isComplete() {
      // Complete when all questions have answers, or when explicitly submitted
      return state.questions.every((q) => q.id in state.answers);
    },
    get progress() {
      const answered = state.questions.filter((q) => q.id in state.answers).length;
      return {
        current: Math.min(answered + 1, state.questions.length),
        total: state.questions.length,
      };
    },

    subscribe(listener: () => void): () => void {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },

    async answer(value: string | number): Promise<void> {
      const question = this.currentQuestion;
      if (!question) {
        return;
      }
      state.answers[question.id] = value;
      state.state = "collecting";
      await persist();
      notify();
    },

    async next(): Promise<void> {
      if (state.index < state.questions.length - 1) {
        state.index += 1;
        state.state = "asking";
        await persist();
        notify();
      } else {
        state.state = "collecting";
        notify();
      }
    },

    async previous(): Promise<void> {
      if (state.index > 0) {
        state.index -= 1;
        state.state = "asking";
        await persist();
        notify();
      }
    },

    async submit(): Promise<void> {
      state.state = "submitted";
      await persist();
      notify();
    },

    async cancel(): Promise<void> {
      state.state = "cancelled";
      await persist();
      notify();
    },
  };
}

export async function restoreInterviewConductor(
  jobId: string,
  persistence: InterviewPersistence,
): Promise<InterviewConductor | null> {
  const draft = await persistence.loadDraft(jobId);
  if (!draft) {
    return null;
  }
  // Reconstruct the full conductor state including questions
  const initialState: Partial<InterviewConductorState> = {
    ...draft,
    questions: DEFAULT_QUESTIONS,
  };
  return createInterviewConductor(jobId, persistence, initialState);
}