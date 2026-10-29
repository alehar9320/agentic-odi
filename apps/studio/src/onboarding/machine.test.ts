import { describe, expect, it } from "vitest";

import {
  LAST_STEP_INDEX,
  advanceTour,
  createOnboardingState,
  finishTour,
  retreatTour,
  selectGoal,
  startTour,
  stepAt,
} from "./machine";
import {
  ONBOARDING_STORAGE_KEY,
  clearOnboardingState,
  readOnboardingState,
  writeOnboardingState,
  type OnboardingStorage,
} from "./storage";

function memoryStorage(seed: Record<string, string> = {}): OnboardingStorage & {
  values: Map<string, string>;
} {
  const values = new Map(Object.entries(seed));
  return {
    values,
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => {
      values.set(key, value);
    },
    removeItem: (key: string) => {
      values.delete(key);
    },
  };
}

describe("onboarding machine", () => {
  it("starts pending on the welcome step with no goal", () => {
    expect(createOnboardingState()).toEqual({
      status: "pending",
      step: 0,
      goal: null,
      version: 1,
    });
  });

  it("moves forward through the flow", () => {
    const advanced = advanceTour(createOnboardingState());
    expect(advanced.step).toBe(1);
    expect(advanced.status).toBe("active");
    expect(stepAt(advanced.step)).toBe("goal");
  });

  it("will not leave the starting-point step without a choice", () => {
    const onGoal = advanceTour(createOnboardingState());
    expect(advanceTour(onGoal)).toEqual(onGoal);

    const chosen = selectGoal(onGoal, "find-opportunity");
    expect(advanceTour(chosen).step).toBe(2);
  });

  it("clamps at both ends", () => {
    expect(retreatTour(createOnboardingState()).step).toBe(0);
    const atEnd = {
      ...createOnboardingState(),
      step: LAST_STEP_INDEX,
      goal: "have-opportunity" as const,
    };
    expect(advanceTour(atEnd).step).toBe(LAST_STEP_INDEX);
  });

  it("freezes finished tours", () => {
    const done = finishTour({ ...createOnboardingState(), step: 2, goal: "have-opportunity" });
    expect(done).toMatchObject({ status: "done", step: LAST_STEP_INDEX });
    expect(advanceTour(done)).toBe(done);
    expect(retreatTour(done)).toBe(done);
  });

  it("restarts from the top with no carried-over goal", () => {
    const done = finishTour({ ...createOnboardingState(), goal: "have-opportunity" });
    expect(startTour(done)).toEqual({
      status: "active",
      step: 0,
      goal: null,
      version: 1,
    });
  });
});

describe("onboarding storage", () => {
  it("round-trips a state", () => {
    const storage = memoryStorage();
    const state = finishTour({ ...createOnboardingState(), goal: "pressure-test", step: 3 });

    writeOnboardingState(state, storage);
    expect(readOnboardingState(storage)).toEqual(state);
  });

  it("treats a missing record as a first run", () => {
    expect(readOnboardingState(memoryStorage())).toBeNull();
  });

  it("treats malformed JSON as a first run", () => {
    const storage = memoryStorage({ [ONBOARDING_STORAGE_KEY]: "{not json" });
    expect(readOnboardingState(storage)).toBeNull();
  });

  it("ignores a record from another tour version", () => {
    const storage = memoryStorage({
      [ONBOARDING_STORAGE_KEY]: JSON.stringify({
        status: "done",
        step: 3,
        goal: "have-opportunity",
        version: 99,
      }),
    });
    expect(readOnboardingState(storage)).toBeNull();
  });

  it("rejects unknown steps, statuses, and goals", () => {
    const cases = [
      { status: "done", step: 9, goal: "have-opportunity", version: 1 },
      { status: "sleeping", step: 1, goal: "have-opportunity", version: 1 },
      { status: "done", step: 3, goal: "define-everything", version: 1 },
      { status: "done", step: 2, goal: null, version: 1 },
    ];
    for (const record of cases) {
      const storage = memoryStorage({
        [ONBOARDING_STORAGE_KEY]: JSON.stringify(record),
      });
      expect(readOnboardingState(storage)).toBeNull();
    }
  });

  it("clears a record", () => {
    const storage = memoryStorage();
    writeOnboardingState(createOnboardingState(), storage);
    clearOnboardingState(storage);
    expect(readOnboardingState(storage)).toBeNull();
  });
});
