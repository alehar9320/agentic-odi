import { describe, expect, it } from "vitest";

import { SCENES } from "./content";
import {
  LAST_SCENE_INDEX,
  advanceTour,
  clampScene,
  createOnboardingState,
  finishTour,
  isFinished,
  retreatTour,
  sceneAt,
  skipSceneTour,
  skipTour,
  startTour,
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
  it("starts pending on the first scene with no reason", () => {
    expect(createOnboardingState()).toEqual({
      status: "pending",
      scene: 0,
      reason: null,
      version: 2,
    });
  });

  it("has exactly three scenes in order", () => {
    expect(SCENES.map((scene) => scene.id)).toEqual(["hear", "score", "place"]);
    expect(LAST_SCENE_INDEX).toBe(2);
  });

  it("walks forward, back, and resumes mid-scene from a stored position", () => {
    const storage = memoryStorage();
    let state = createOnboardingState();

    state = advanceTour(state);
    expect(state).toMatchObject({ status: "active", scene: 1 });
    expect(sceneAt(state.scene)).toBe("score");

    // Leaving mid-scene persists where it stopped.
    writeOnboardingState(state, storage);
    expect(readOnboardingState(storage)).toMatchObject({ status: "active", scene: 1 });

    // Returning resumes at the same scene, not the first.
    const resumed = readOnboardingState(storage);
    expect(resumed && sceneAt(resumed.scene)).toBe("score");

    expect(retreatTour(state).scene).toBe(0);
  });

  it("clamps at both ends", () => {
    expect(retreatTour(createOnboardingState()).scene).toBe(0);
    const atEnd = { ...createOnboardingState(), scene: LAST_SCENE_INDEX };
    expect(advanceTour(atEnd).scene).toBe(LAST_SCENE_INDEX);
    expect(clampScene(9)).toBe(LAST_SCENE_INDEX);
    expect(clampScene(-3)).toBe(0);
    expect(clampScene(Number.NaN)).toBe(0);
  });

  it("skips one scene without ending the tour", () => {
    const skipped = skipSceneTour(createOnboardingState());
    expect(skipped).toMatchObject({ status: "active", scene: 1, reason: null });
  });

  it("records why the tour was skipped, and skipping is terminal", () => {
    const skipped = skipTour(createOnboardingState(), "dismissed");
    expect(skipped).toMatchObject({ status: "skipped", reason: "dismissed" });
    expect(isFinished(skipped)).toBe(true);
    // Nothing moves a skipped tour; it does not nag again.
    expect(advanceTour(skipped)).toBe(skipped);
    expect(retreatTour(skipped)).toBe(skipped);
    expect(skipSceneTour(skipped)).toBe(skipped);
  });

  it("defaults the skip reason to not-now", () => {
    expect(skipTour(createOnboardingState()).reason).toBe("not-now");
  });

  it("freezes finished tours", () => {
    const done = finishTour({ ...createOnboardingState(), scene: 1 });
    expect(done).toMatchObject({ status: "done", scene: LAST_SCENE_INDEX, reason: null });
    expect(advanceTour(done)).toBe(done);
    expect(retreatTour(done)).toBe(done);
  });

  it("restarts from the top with no carried-over reason", () => {
    const done = skipTour({ ...createOnboardingState(), scene: 2 }, "dismissed");
    expect(startTour(done)).toEqual({
      status: "active",
      scene: 0,
      reason: null,
      version: 2,
    });
  });
});

describe("onboarding storage", () => {
  it("round-trips a state", () => {
    const storage = memoryStorage();
    const state = finishTour({ ...createOnboardingState(), scene: 1 });

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
    // The old four-step record reads as a first run rather than migrating.
    const storage = memoryStorage({
      [ONBOARDING_STORAGE_KEY]: JSON.stringify({
        status: "done",
        step: 3,
        goal: "have-opportunity",
        version: 1,
      }),
    });
    expect(readOnboardingState(storage)).toBeNull();
  });

  it("rejects unknown scenes, statuses, and reasons", () => {
    const cases = [
      { status: "done", scene: 9, reason: null, version: 2 },
      { status: "sleeping", scene: 1, reason: null, version: 2 },
      { status: "done", scene: 1, reason: "because", version: 2 },
      // A reason only belongs to a skipped tour.
      { status: "active", scene: 1, reason: "not-now", version: 2 },
      // A skipped tour always records why, so one without a reason is malformed.
      { status: "skipped", scene: 1, reason: null, version: 2 },
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
