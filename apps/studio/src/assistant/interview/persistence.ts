/**
 * The interview draft store (issue #402).
 *
 * An interview that was half-answered when the app closed should reopen at the
 * same question with every answer intact. This module owns that: it turns the
 * conductor's state into a draft record, writes it through the local store on a
 * debounce so a burst of keystrokes is one write, deletes it once the interview
 * is terminal, and reads the most recent draft for a job back on mount.
 *
 * It holds no domain types and decides nothing about what an answer means: the
 * draft is `{ id, jobId, answers, index, updatedAt }`, the same shape the
 * conductor already holds. Every entry point fails soft — a store that throws
 * leaves the interview usable in memory and surfaces no banner.
 */

import type { InterviewDraft } from "../../bff/store/types";

/** The slice of `LocalStore` a draft needs; a test can pass a plain object. */
export interface DraftStore {
  listInterviewDrafts(jobId?: string): Promise<InterviewDraft[]>;
  putInterviewDraft(draft: InterviewDraft): Promise<void>;
  deleteInterviewDraft(id: string): Promise<void>;
}

/** The part of the conductor's state a draft is made of. */
export interface DraftState {
  answers: Record<string, string | number>;
  index: number;
  status: string;
}

/**
 * A state that ends the interview: the draft is deleted rather than written, so
 * a submitted interview leaves nothing behind. `submitting` counts because the
 * submit has already been accepted and its answers are on their way to records.
 */
const TERMINAL: ReadonlySet<string> = new Set([
  "submitting",
  "done",
  "failed",
  "abandoned",
]);

/** Only `collecting` is a draft; `idle` and `asking` have nothing to resume. */
const WRITABLE = "collecting";

/** Build the stored draft from the conductor's state. Pure. */
export function draftFromState(
  id: string,
  jobId: string,
  state: DraftState,
  updatedAt: string,
): InterviewDraft {
  return {
    id,
    jobId,
    answers: { ...state.answers },
    index: state.index,
    updatedAt,
  };
}

/**
 * The most recent draft for `jobId`, or null. A draft for another job is never
 * returned, and a store failure reads as "no draft" rather than as an error —
 * an unreadable draft must not block a fresh interview.
 */
export async function latestDraft(
  store: DraftStore,
  jobId: string,
): Promise<InterviewDraft | null> {
  try {
    const drafts = await store.listInterviewDrafts(jobId);
    return drafts[0] ?? null;
  } catch {
    return null;
  }
}

export interface DraftWriter {
  /** Record the current state; coalesced into at most one write per window. */
  write(state: DraftState): void;
  /** Delete the draft immediately (a terminal state, or an explicit reset). */
  clear(): Promise<void>;
  /** Write any pending draft now, then resolve. Used by tests and on unload. */
  flush(): Promise<void>;
}

export interface DraftWriterOptions {
  store: DraftStore;
  interviewId: string;
  jobId: string;
  /** The write window. At most one write lands per `debounceMs`. */
  debounceMs?: number;
  /** The clock for `updatedAt`; a test pins it. */
  now?: () => string;
}

/**
 * A debounced writer over one interview's draft.
 *
 * The first change in a window schedules the write; later changes in the same
 * window replace the pending record instead of scheduling a second timer, so
 * three answers inside a second are one write. Nothing here rejects: a failing
 * store is swallowed, and the interview carries on in memory.
 */
export function createDraftWriter(options: DraftWriterOptions): DraftWriter {
  const { store, interviewId, jobId, debounceMs = 1_000, now = () => new Date().toISOString() } =
    options;

  let pending: InterviewDraft | null = null;
  let timer: ReturnType<typeof setTimeout> | null = null;
  let inFlight: Promise<void> = Promise.resolve();

  function persist(draft: InterviewDraft): void {
    // Chain onto the previous write so a slow store cannot reorder two drafts.
    inFlight = inFlight
      .then(() => store.putInterviewDraft(draft))
      .catch(() => undefined);
  }

  function flushNow(): void {
    if (timer !== null) {
      clearTimeout(timer);
      timer = null;
    }
    if (pending) {
      persist(pending);
      pending = null;
    }
  }

  return {
    write(state) {
      if (TERMINAL.has(state.status)) {
        pending = null;
        flushNow();
        inFlight = inFlight.then(() => store.deleteInterviewDraft(interviewId)).catch(() => undefined);
        return;
      }
      if (state.status !== WRITABLE) {
        return;
      }
      pending = draftFromState(interviewId, jobId, state, now());
      if (timer === null) {
        timer = setTimeout(flushNow, debounceMs);
      }
    },
    async clear() {
      pending = null;
      flushNow();
      try {
        await store.deleteInterviewDraft(interviewId);
      } catch {
        // Fail soft: a draft that will not delete is not worth an interruption.
      }
    },
    async flush() {
      flushNow();
      await inFlight;
    },
  };
}
