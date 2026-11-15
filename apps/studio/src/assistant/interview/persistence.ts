import { nowIso } from "../../bff/id";
import type { InterviewDraft } from "../../bff/store/types";
import type { LocalStore } from "../../bff/store/types";

const DEBOUNCE_MS = 1000;

export type InterviewState = "idle" | "asking" | "collecting" | "submitted" | "cancelled";

export interface InterviewQuestion {
  id: string;
  text: string;
  kind: "text" | "number" | "scale";
  min?: number;
  max?: number;
  step?: number;
}

export interface InterviewDraftData {
  id: string;
  jobId: string;
  answers: Record<string, string | number>;
  index: number;
  updatedAt: string;
}

export interface InterviewConductorState {
  id: string;
  jobId: string;
  state: InterviewState;
  answers: Record<string, string | number>;
  index: number;
  questions: readonly InterviewQuestion[];
}

function toStored(draft: InterviewConductorState): InterviewDraft {
  return {
    id: draft.id,
    jobId: draft.jobId,
    answers: draft.answers,
    index: draft.index,
    updatedAt: nowIso(),
  };
}

function fromStored(stored: InterviewDraft): InterviewConductorState {
  return {
    id: stored.id,
    jobId: stored.jobId,
    state: "idle",
    answers: stored.answers,
    index: stored.index,
    questions: [],
  };
}

export class InterviewPersistence {
  private readonly store: LocalStore;
  private debounceTimers = new Map<string, ReturnType<typeof setTimeout>>();
  private pendingWrites = new Map<string, InterviewConductorState>();

  constructor(store: LocalStore) {
    this.store = store;
  }

  async saveDraft(state: InterviewConductorState): Promise<void> {
    const key = state.jobId;
    const existingTimer = this.debounceTimers.get(key);
    if (existingTimer) {
      clearTimeout(existingTimer);
    }
    this.pendingWrites.set(key, state);

    const timer = setTimeout(async () => {
      this.debounceTimers.delete(key);
      const pending = this.pendingWrites.get(key);
      if (!pending) {
        return;
      }
      this.pendingWrites.delete(key);
      try {
        await this.store.putInterviewDraft(toStored(pending));
      } catch {
        // Fail soft: a store error leaves the interview usable in memory.
        // The draft will be retried on the next transition.
      }
    }, DEBOUNCE_MS);

    this.debounceTimers.set(key, timer);
  }

  async saveDraftImmediately(state: InterviewConductorState): Promise<void> {
    const key = state.jobId;
    const existingTimer = this.debounceTimers.get(key);
    if (existingTimer) {
      clearTimeout(existingTimer);
      this.debounceTimers.delete(key);
    }
    this.pendingWrites.delete(key);
    try {
      await this.store.putInterviewDraft(toStored(state));
    } catch {
      // Fail soft: a store error leaves the interview usable in memory.
    }
  }

  async loadDraft(jobId: string): Promise<InterviewConductorState | undefined> {
    try {
      const stored = await this.store.getInterviewDraft(jobId);
      if (!stored) {
        return undefined;
      }
      return fromStored(stored);
    } catch {
      // Fail soft: a store error leaves the interview usable in memory.
      return undefined;
    }
  }

  async deleteDraft(jobId: string): Promise<void> {
    const existingTimer = this.debounceTimers.get(jobId);
    if (existingTimer) {
      clearTimeout(existingTimer);
      this.debounceTimers.delete(jobId);
    }
    this.pendingWrites.delete(jobId);
    try {
      await this.store.deleteInterviewDraft(jobId);
    } catch {
      // Fail soft: a store error leaves the interview usable in memory.
    }
  }

  flush(): void {
    for (const [key, timer] of this.debounceTimers.entries()) {
      clearTimeout(timer);
      const pending = this.pendingWrites.get(key);
      if (pending) {
        this.pendingWrites.delete(key);
        this.store.putInterviewDraft(toStored(pending)).catch(() => {
          // Fail soft
        });
      }
    }
  }
}