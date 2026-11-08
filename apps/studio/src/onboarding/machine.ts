import { SCENES, type SceneId } from "./content";

/**
 * Pure flow rules for the product tour. No React, no storage, no DOM — the
 * whole sequence can be reasoned about and tested as plain functions.
 *
 * Nothing here opens the tour. Opening is a deliberate action, handled by the
 * provider; these functions only move through the flow once it is open.
 */

export const ONBOARDING_VERSION = 2;
export const LAST_SCENE_INDEX = SCENES.length - 1;

export type OnboardingStatus = "pending" | "active" | "done" | "skipped";

/** Why a tour was left. A skip is terminal and keeps its reason. */
export type SkipReason = "not-now" | "dismissed";

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

export function sceneAt(scene: number): SceneId {
  return SCENES[clampScene(scene)].id;
}

export function isFinished(state: OnboardingState): boolean {
  return state.status === "done" || state.status === "skipped";
}

/** Replay: start from the top, forget how the last run ended. */
export function startTour(state: OnboardingState): OnboardingState {
  return { ...state, status: "active", scene: 0, reason: null };
}

export function advanceTour(state: OnboardingState): OnboardingState {
  if (isFinished(state)) {
    return state;
  }
  return { ...state, status: "active", scene: clampScene(state.scene + 1) };
}

/** Move past one scene without leaving the tour; it never finishes the flow. */
export function skipSceneTour(state: OnboardingState): OnboardingState {
  if (isFinished(state)) {
    return state;
  }
  return { ...state, status: "active", scene: clampScene(state.scene + 1) };
}

export function retreatTour(state: OnboardingState): OnboardingState {
  if (isFinished(state)) {
    return state;
  }
  return { ...state, status: "active", scene: clampScene(state.scene - 1) };
}

export function finishTour(state: OnboardingState): OnboardingState {
  return { ...state, status: "done", scene: LAST_SCENE_INDEX, reason: null };
}

/**
 * Leave the tour for good. `skipped` is terminal and stores why, so the tour
 * does not nag again and a later reader can tell a deliberate exit from a
 * dismissal.
 */
export function skipTour(
  state: OnboardingState,
  reason: SkipReason = "not-now",
): OnboardingState {
  return { ...state, status: "skipped", reason };
}
