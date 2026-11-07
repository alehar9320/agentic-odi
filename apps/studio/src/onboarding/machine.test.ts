import { describe, expect, it } from "vitest";

import { SCENES } from "./content";
import {
  LAST_SCENE_INDEX,
  advanceTour,
  createOnboardingState,
  finishTour,
  retreatTour,
  skipSceneTour,
  skipTour,
  startTour,
  sceneAt,
  type OnboardingState,
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

/** Walk the tour from the top, recording the scene id at each stop. */
function walk(state: OnboardingState): string[] {
  const seen: string[] = [sceneAt(state.scene)];
  for (let i = 0; i < SCENES.length + 2; i += 1) {
    const next = advanceTour(state);
    if (next.scene === state.scene) {
      break;
    }
    state = next;
    seen.push(sceneAt(state.scene));
  }
  return seen;
}

describe("onboarding machine", () => {
  it("has exactly three scenes, in order", () => {
    expect(SCENES.map((scene) => scene.id)).toEqual(["hear", "score", "place"]);
    expect(LAST_SCENE_INDEX).toBe(2);
  });

  it("starts pending on the first scene with no reason", () => {
    expect(createOnboardingState()).toEqual({
      status: "pending",
      scene: 0,
      reason: null,
      version: 2,
    });
  });

  it("walks forward through every scene and stops at the last", () => {
    expect(walk(createOnboardingState())).toEqual(["hear", "score", "place"]);
  });

  it("walks back to where it was", () => {
    let state = createOnboardingState();
    state = advanceTour(state);
    state = advanceTour(state);
    expect(state.scene).toBe(2);

    state = retreatTour(state);
    expect(state.scene).toBe(1);
    expect(sceneAt(state.scene)).toBe("score");
    state = retreatTour(state);
    state = retreatTour(state);
    expect(state.scene).toBe(0);
  });

  it("clamps at both ends", () => {
    expect(retreatTour(createOnboardingState()).scene).toBe(0);
    const atEnd = { ...createOnboardingState(), scene: LAST_SCENE_INDEX };
    expect(advanceTour(atEnd).scene).toBe(LAST_SCENE_INDEX);
  });

  it("skips a scene without leaving the tour", () => {
    const skipped = skipSceneTour(createOnboardingState());
    expect(skipped).toMatchObject({ status: "open", scene: 1, reason: null });
  });

  it("records why the tour was skipped and stays terminal", () => {
    const left = skipTour(createOnboardingState(), "not-now");
    expect(left).toMatchObject({ status: "skipped", reason: "not-now" });

    const dismissed = skipTour(createOnboardingState(), "dismissed");
    expect(dismissed).toMatchObject({ status: "skipped", reason: "dismissed" });

    // A finished tour is frozen: no advance, no retreat, no scene skip.
    expect(advanceTour(left)).toBe(left);
    expect(retreatTour(left)).toBe(left);
    expect(skipSceneTour(left)).toBe(left);
  });

  it("finishes on the last scene", () => {
    const done = finishTour({ ...createOnboardingState(), scene: 1 });
    expect(done).toMatchObject({ status: "done", scene: LAST_SCENE_INDEX, reason: null });
  });

  it("restarts from the top with no carried-over reason", () => {
    const left = skipTour({ ...createOnboardingState(), scene: 2 }, "dismissed");
    expect(startTour(left)).toEqual({
      status: "open",
      scene: 0,
      reason: null,
      version: 2,
    });
  });
});

describe("onboarding storage", () => {
  it("round-trips an open state", () => {
    const storage = memoryStorage();
    const state = advanceTour(createOnboardingState());
    writeOnboardingState(state, storage);
    expect(readOnboardingState(storage)).toEqual(state);
  });

  it("round-trips a skipped state with its reason", () => {
    const storage = memoryStorage();
    const state = skipTour({ ...createOnboardingState(), scene: 1 }, "dismissed");
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

  it("ignores the old four-step shape", () => {
    const storage = memoryStorage({
      [ONBOARDING_STORAGE_KEY]: JSON.stringify({
        status: "active",
        step: 2,
        goal: "have-opportunity",
        version: 1,
      }),
    });
    expect(readOnboardingState(storage)).toBeNull();
  });

  it("rejects unknown scenes, statuses, and reasons", () => {
    const cases = [
      { status: "open", scene: 9, reason: null, version: 2 },
      { status: "sleeping", scene: 1, reason: null, version: 2 },
      { status: "skipped", scene: 1, reason: "bored", version: 2 },
      // A reason is only meaningful on a skipped tour.
      { status: "open", scene: 1, reason: "not-now", version: 2 },
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
