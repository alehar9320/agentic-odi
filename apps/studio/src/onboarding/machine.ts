import { SCENES, type TourSceneId } from "./content";

/**
 * Pure flow rules for the product tour. No React, no storage, no DOM — the
 * whole sequence can be reasoned about and tested as plain functions.
 *
 * Nothing here opens the tour. Opening is a deliberate action, handled by the
 * provider; these functions only move through the flow once it is open.
 */

/** Bumped when the stored shape changes. An older record reads as a first run. */
export const ONBOARDING_VERSION = 2;
export const LAST_SCENE_INDEX = SCENES.length - 1;

export type OnboardingStatus = "pending" | "open" | "done" | "skipped";

/**
 * Why a person left the tour. Recorded so a skip is a signal rather than a
 * shrug; it is never asked for, so leaving stays one click.
 */
export type SkipReason =
  /** The person used the tour's own skip control. */
  | "not-now"
  /** The person dismissed the tour with Escape. */
  | "dismissed";

export interface OnboardingState {
  status: OnboardingStatus;
  scene: number;
  reason: SkipReason | null;
  version: number;
}

export function createOnboardingState(
  overrides: Partial<OnboardingState> = {},
): OnboardingState {
  return {
    status: "pending",
    scene: 0,
    reason: null,
    version: ONBOARDING_VERSION,
    ...overrides,
  };
}

export function clampScene(scene: number): number {
  if (!Number.isFinite(scene)) {
    return 0;
  }
  return Math.min(LAST_SCENE_INDEX, Math.max(0, Math.trunc(scene)));
}

export function sceneAt(scene: number): TourSceneId {
  return SCENES[clampScene(scene)].id;
}

export function isFinished(state: OnboardingState): boolean {
  return state.status === "done" || state.status === "skipped";
}

/** Replay: start from the top, forget the previous reason. */
export function startTour(state: OnboardingState): OnboardingState {
  return { ...state, status: "open", scene: 0, reason: null };
}

export function advanceTour(state: OnboardingState): OnboardingState {
  if (isFinished(state)) {
    return state;
  }
  return { ...state, status: "open", scene: clampScene(state.scene + 1) };
}

/** Move past one scene without leaving the tour; it never finishes the flow. */
export function skipSceneTour(state: OnboardingState): OnboardingState {
  if (isFinished(state)) {
    return state;
  }
  return { ...state, status: "open", scene: clampScene(state.scene + 1) };
}

export function retreatTour(state: OnboardingState): OnboardingState {
  if (isFinished(state)) {
    return state;
  }
  return { ...state, status: "open", scene: clampScene(state.scene - 1) };
}

export function finishTour(state: OnboardingState): OnboardingState {
  return { ...state, status: "done", scene: LAST_SCENE_INDEX, reason: null };
}

/** Leaving the tour, with the reason recorded. Terminal until replayed. */
export function skipTour(state: OnboardingState, reason: SkipReason): OnboardingState {
  return { ...state, status: "skipped", reason };
}
