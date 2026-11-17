/**
 * The interview draft's rules (issue #402).
 *
 * The draft is what makes a reload cheap: the same answers, the same question,
 * and nothing left behind once the interview is submitted. These tests pin the
 * four promises the issue makes — the write is debounced to one per window, a
 * terminal state deletes the draft, another job's draft is ignored, and a store
 * that throws never blocks the interview.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { MemoryLocalStore } from "../../bff/store/memoryStore";
import type { InterviewDraft } from "../../bff/store/types";
import { createDraftWriter, draftFromState, latestDraft, type DraftStore } from "./persistence";

/** A store whose draft calls are counted, and can be made to reject. */
function draftStore(options: { failWrites?: boolean } = {}) {
  const written: InterviewDraft[] = [];
  const deleted: string[] = [];
  const store: DraftStore = {
    listInterviewDrafts: vi.fn(async (jobId?: string) =>
      written
        .filter((draft) => !jobId || draft.jobId === jobId)
        .sort((left, right) => right.updatedAt.localeCompare(left.updatedAt)),
    ),
    putInterviewDraft: vi.fn(async (draft) => {
      if (options.failWrites) {
        throw new Error("the store refused the draft");
      }
      const index = written.findIndex((existing) => existing.id === draft.id);
      if (index >= 0) {
        written[index] = draft;
      } else {
        written.push(draft);
      }
    }),
    deleteInterviewDraft: vi.fn(async (id) => {
      deleted.push(id);
      const index = written.findIndex((draft) => draft.id === id);
      if (index >= 0) {
        written.splice(index, 1);
      }
    }),
  };
  return { store, written, deleted };
}

const collecting = (overrides: Partial<{ answers: Record<string, string | number>; index: number }> = {}) => ({
  status: "collecting",
  answers: { job: "A job", importance: 8 },
  index: 1,
  ...overrides,
});

describe("interview draft — the record", () => {
  it("round-trips a draft with a numeric answer", () => {
    const draft = draftFromState("i-1", "j-1", collecting(), "2026-01-01T00:00:00.000Z");
    expect(draft).toEqual({
      id: "i-1",
      jobId: "j-1",
      answers: { job: "A job", importance: 8 },
      index: 1,
      updatedAt: "2026-01-01T00:00:00.000Z",
    });
    expect(typeof draft.answers.importance).toBe("number");
  });
});

describe("interview draft — the writer", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("writes once for three answers inside the window", async () => {
    const { store, written } = draftStore();
    const writer = createDraftWriter({
      store,
      interviewId: "i-1",
      jobId: "j-1",
      debounceMs: 1_000,
    });

    writer.write(collecting({ answers: { job: "A" }, index: 0 }));
    writer.write(collecting({ answers: { job: "A", outcome: "B" }, index: 1 }));
    writer.write(collecting({ answers: { job: "A", outcome: "B", importance: 7 }, index: 2 }));
    expect(store.putInterviewDraft).not.toHaveBeenCalled();

    await vi.advanceTimersByTimeAsync(1_000);
    await writer.flush();

    expect(store.putInterviewDraft).toHaveBeenCalledTimes(1);
    expect(written).toHaveLength(1);
    expect(written[0].answers).toEqual({ job: "A", outcome: "B", importance: 7 });
    expect(written[0].index).toBe(2);
  });

  it("deletes the draft when the interview reaches a terminal state", async () => {
    const { store, deleted } = draftStore();
    const writer = createDraftWriter({ store, interviewId: "i-1", jobId: "j-1" });

    writer.write(collecting());
    await vi.advanceTimersByTimeAsync(1_000);
    await writer.flush();
    expect(store.putInterviewDraft).toHaveBeenCalledTimes(1);

    writer.write({ ...collecting(), status: "submitting" });
    await writer.flush();

    expect(deleted).toEqual(["i-1"]);
    // A terminal state never writes the draft it is deleting.
    expect(store.putInterviewDraft).toHaveBeenCalledTimes(1);
  });

  it("ignores a state with nothing to resume", async () => {
    const { store } = draftStore();
    const writer = createDraftWriter({ store, interviewId: "i-1", jobId: "j-1" });

    writer.write({ status: "asking", answers: {}, index: 0 });
    await vi.advanceTimersByTimeAsync(2_000);

    expect(store.putInterviewDraft).not.toHaveBeenCalled();
  });
});

describe("interview draft — reading it back", () => {
  it("returns the most recent draft for the job and ignores another job's", async () => {
    const store = new MemoryLocalStore();
    await store.putInterviewDraft({
      id: "draft-other",
      jobId: "j-2",
      answers: { job: "Other" },
      index: 0,
      updatedAt: "2026-01-05T00:00:00.000Z",
    });
    await store.putInterviewDraft({
      id: "draft-old",
      jobId: "j-1",
      answers: { job: "A job" },
      index: 0,
      updatedAt: "2026-01-01T00:00:00.000Z",
    });
    await store.putInterviewDraft({
      id: "draft-new",
      jobId: "j-1",
      answers: { job: "A job", importance: 9 },
      index: 2,
      updatedAt: "2026-01-02T00:00:00.000Z",
    });

    const draft = await latestDraft(store, "j-1");
    expect(draft?.id).toBe("draft-new");
    expect(draft?.answers).toEqual({ job: "A job", importance: 9 });
    expect(await latestDraft(store, "j-none")).toBeNull();
  });

  it("reads a store failure as no draft rather than as an error", async () => {
    const store: DraftStore = {
      listInterviewDrafts: async () => {
        throw new Error("the store is unavailable");
      },
      putInterviewDraft: async () => undefined,
      deleteInterviewDraft: async () => undefined,
    };
    await expect(latestDraft(store, "j-1")).resolves.toBeNull();
  });
});

describe("interview draft — failing soft", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("completes the write path with a store that throws", async () => {
    const { store } = draftStore({ failWrites: true });
    const writer = createDraftWriter({ store, interviewId: "i-1", jobId: "j-1" });

    writer.write(collecting());
    await vi.advanceTimersByTimeAsync(1_000);

    // The failing write is swallowed: flushing resolves instead of rejecting.
    await expect(writer.flush()).resolves.toBeUndefined();
  });
});
