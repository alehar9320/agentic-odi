import { afterEach, describe, expect, it, vi } from "vitest";

import { InterviewPersistence } from "./persistence";
import { MemoryLocalStore } from "../../bff/store/memoryStore";

async function makeStore() {
  return new MemoryLocalStore();
}

afterEach(() => {
  vi.useRealTimers();
});

describe("InterviewPersistence", () => {
  it("round-trips a draft with a numeric answer", async () => {
    const store = await makeStore();
    const persistence = new InterviewPersistence(store);

    const state = {
      id: "test-1",
      jobId: "job-1",
      state: "collecting" as const,
      answers: { importance: 8, satisfaction: 3 },
      index: 4,
      questions: [],
    };

    await persistence.saveDraftImmediately(state);
    const loaded = await persistence.loadDraft("job-1");

    expect(loaded).toBeDefined();
    expect(loaded?.id).toBe("test-1");
    expect(loaded?.jobId).toBe("job-1");
    expect(loaded?.answers.importance).toBe(8);
    expect(loaded?.answers.satisfaction).toBe(3);
    expect(loaded?.index).toBe(4);
  });

  it("debounces writes to at most one per second", async () => {
    vi.useFakeTimers();
    const store = await makeStore();
    const persistence = new InterviewPersistence(store);

    const state1 = {
      id: "test-1",
      jobId: "job-1",
      state: "collecting" as const,
      answers: { q1: "a" },
      index: 0,
      questions: [],
    };
    const state2 = {
      id: "test-1",
      jobId: "job-1",
      state: "collecting" as const,
      answers: { q1: "a", q2: "b" },
      index: 1,
      questions: [],
    };
    const state3 = {
      id: "test-1",
      jobId: "job-1",
      state: "collecting" as const,
      answers: { q1: "a", q2: "b", q3: "c" },
      index: 2,
      questions: [],
    };

    await persistence.saveDraft(state1);
    await persistence.saveDraft(state2);
    await persistence.saveDraft(state3);

    // Advance time by less than debounce - nothing written yet
    vi.advanceTimersByTime(500);
    let loaded = await persistence.loadDraft("job-1");
    expect(loaded).toBeUndefined();

    // Advance past debounce - only the last state should be written
    vi.advanceTimersByTime(600);
    loaded = await persistence.loadDraft("job-1");
    expect(loaded).toBeDefined();
    expect(loaded?.answers).toEqual({ q1: "a", q2: "b", q3: "c" });
    expect(loaded?.index).toBe(2);
  });

  it("deletes draft on terminal state", async () => {
    const store = await makeStore();
    const persistence = new InterviewPersistence(store);

    const state = {
      id: "test-1",
      jobId: "job-1",
      state: "collecting" as const,
      answers: { q1: "a" },
      index: 0,
      questions: [],
    };

    await persistence.saveDraftImmediately(state);
    let loaded = await persistence.loadDraft("job-1");
    expect(loaded).toBeDefined();

    await persistence.deleteDraft("job-1");
    loaded = await persistence.loadDraft("job-1");
    expect(loaded).toBeUndefined();
  });

  it("ignores draft for another job", async () => {
    const store = await makeStore();
    const persistence = new InterviewPersistence(store);

    const state1 = {
      id: "test-1",
      jobId: "job-1",
      state: "collecting" as const,
      answers: { q1: "a" },
      index: 0,
      questions: [],
    };
    const state2 = {
      id: "test-2",
      jobId: "job-2",
      state: "collecting" as const,
      answers: { q1: "b" },
      index: 0,
      questions: [],
    };

    await persistence.saveDraftImmediately(state1);
    await persistence.saveDraftImmediately(state2);

    const loaded1 = await persistence.loadDraft("job-1");
    const loaded2 = await persistence.loadDraft("job-2");

    expect(loaded1?.answers.q1).toBe("a");
    expect(loaded2?.answers.q1).toBe("b");
  });

  it("fails soft on store error", async () => {
    const store = await makeStore();
    const persistence = new InterviewPersistence(store);

    // Break the store
    const originalPut = store.putInterviewDraft.bind(store);
    store.putInterviewDraft = vi.fn().mockRejectedValue(new Error("Store failed"));

    const state = {
      id: "test-1",
      jobId: "job-1",
      state: "collecting" as const,
      answers: { q1: "a" },
      index: 0,
      questions: [],
    };

    // Should not throw
    await expect(persistence.saveDraftImmediately(state)).resolves.toBeUndefined();
    await expect(persistence.loadDraft("job-1")).resolves.toBeUndefined();
    await expect(persistence.deleteDraft("job-1")).resolves.toBeUndefined();

    // Restore store
    store.putInterviewDraft = originalPut;
    await persistence.saveDraftImmediately(state);
    const loaded = await persistence.loadDraft("job-1");
    expect(loaded).toBeDefined();
  });
});