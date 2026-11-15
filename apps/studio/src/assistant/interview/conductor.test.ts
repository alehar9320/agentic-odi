import { describe, expect, it } from "vitest";

import { createInterviewConductor, restoreInterviewConductor } from "./conductor";
import { InterviewPersistence } from "./persistence";
import { MemoryLocalStore } from "../../bff/store/memoryStore";

async function makeStore() {
  return new MemoryLocalStore();
}

describe("InterviewConductor", () => {
  it("starts at the first question", async () => {
    const store = await makeStore();
    const persistence = new InterviewPersistence(store);
    const conductor = createInterviewConductor("job-1", persistence);

    expect(conductor.state.index).toBe(0);
    expect(conductor.currentQuestion?.id).toBe("role");
    expect(conductor.progress.current).toBe(1);
    expect(conductor.progress.total).toBe(6);
    expect(conductor.isComplete).toBe(false);
  });

  it("advances through questions on answer and next", async () => {
    const store = await makeStore();
    const persistence = new InterviewPersistence(store);
    const conductor = createInterviewConductor("job-1", persistence);

    await conductor.answer("Product Manager");
    expect(conductor.state.answers.role).toBe("Product Manager");

    await conductor.next();
    expect(conductor.state.index).toBe(1);
    expect(conductor.currentQuestion?.id).toBe("context");
  });

  it("goes back to previous question", async () => {
    const store = await makeStore();
    const persistence = new InterviewPersistence(store);
    const conductor = createInterviewConductor("job-1", persistence);

    await conductor.next();
    expect(conductor.state.index).toBe(1);

    await conductor.previous();
    expect(conductor.state.index).toBe(0);
  });

  it("marks complete after last question", async () => {
    const store = await makeStore();
    const persistence = new InterviewPersistence(store);
    const conductor = createInterviewConductor("job-1", persistence);

    for (let i = 0; i < 6; i++) {
      const q = conductor.currentQuestion;
      if (q?.kind === "number") {
        await conductor.answer(5);
      } else {
        await conductor.answer("test");
      }
      if (i < 5) {
        await conductor.next();
      }
    }

    expect(conductor.isComplete).toBe(true);
  });

  it("persists draft on each answer", async () => {
    const store = await makeStore();
    const persistence = new InterviewPersistence(store);
    const conductor = createInterviewConductor("job-1", persistence);

    await conductor.answer("Product Manager");
    await conductor.next();
    await conductor.answer("Working on a new feature");

    const loaded = await persistence.loadDraft("job-1");
    expect(loaded).toBeDefined();
    expect(loaded?.answers.role).toBe("Product Manager");
    expect(loaded?.answers.context).toBe("Working on a new feature");
    expect(loaded?.index).toBe(1);
  });

  it("deletes draft on submit", async () => {
    const store = await makeStore();
    const persistence = new InterviewPersistence(store);
    const conductor = createInterviewConductor("job-1", persistence);

    await conductor.answer("test");
    await conductor.submit();

    const loaded = await persistence.loadDraft("job-1");
    expect(loaded).toBeUndefined();
  });

  it("deletes draft on cancel", async () => {
    const store = await makeStore();
    const persistence = new InterviewPersistence(store);
    const conductor = createInterviewConductor("job-1", persistence);

    await conductor.answer("test");
    await conductor.cancel();

    const loaded = await persistence.loadDraft("job-1");
    expect(loaded).toBeUndefined();
  });

  it("restores conductor from draft", async () => {
    const store = await makeStore();
    const persistence = new InterviewPersistence(store);

    // Create and persist a draft
    const conductor1 = createInterviewConductor("job-1", persistence);
    await conductor1.answer("Product Manager");
    await conductor1.next();
    await conductor1.answer("Context here");
    await conductor1.next();

    // Restore in a new conductor
    const conductor2 = await restoreInterviewConductor("job-1", persistence);

    expect(conductor2).not.toBeNull();
    expect(conductor2!.state.answers.role).toBe("Product Manager");
    expect(conductor2!.state.answers.context).toBe("Context here");
    expect(conductor2!.state.index).toBe(2);
    expect(conductor2!.state.jobId).toBe("job-1");
  });

  it("returns null when no draft exists", async () => {
    const store = await makeStore();
    const persistence = new InterviewPersistence(store);

    const conductor = await restoreInterviewConductor("job-nonexistent", persistence);
    expect(conductor).toBeNull();
  });

  it("ignores draft for another job", async () => {
    const store = await makeStore();
    const persistence = new InterviewPersistence(store);

    const conductor1 = createInterviewConductor("job-1", persistence);
    await conductor1.answer("Job 1 answer");

    const conductor2 = await restoreInterviewConductor("job-2", persistence);
    expect(conductor2).toBeNull();
  });
});