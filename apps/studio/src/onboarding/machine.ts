import { GOAL_STEP_INDEX, STEPS, type GoalId, type WizardStepId } from "./content";

/**
 * Pure flow rules for the product tour. No React, no storage, no DOM — the
 * whole sequence can be reasoned about and tested as plain functions.
 *
 * Nothing here opens the tour. Opening is a deliberate action, handled by the
 * provider; these functions only move through the flow once it is open.
 */

export const ONBOARDING_VERSION = 1;
export const LAST_STEP_INDEX = STEPS.length - 1;

export type OnboardingStatus = "pending" | "active" | "done" | "skipped";

export interface OnboardingState {
  status: OnboardingStatus;
  step: number;
  goal: GoalId | null;
  version: number;
}

export function createOnboardingState(
  overrides: Partial<OnboardingState> = {},
): OnboardingState {
  return {
    status: "pending",
    step: 0,
    goal: null,
    version: ONBOARDING_VERSION,
    ...overrides,
  };
}

export function clampStep(step: number): number {
  if (!Number.isFinite(step)) {
    return 0;
  }
  return Math.min(LAST_STEP_INDEX, Math.max(0, Math.trunc(step)));
}

export function stepAt(step: number): WizardStepId {
  return STEPS[clampStep(step)].id;
}

export function isFinished(state: OnboardingState): boolean {
  return state.status === "done" || state.status === "skipped";
}

/** Replay: start from the top, forget the previous choice. */
export function startTour(state: OnboardingState): OnboardingState {
  return { ...state, status: "active", step: 0, goal: null };
}

export function advanceTour(state: OnboardingState): OnboardingState {
  if (isFinished(state)) {
    return state;
  }
  // The flow will not leave the starting-point step without a choice.
  if (state.step === GOAL_STEP_INDEX && state.goal === null) {
    return state;
  }
  return { ...state, status: "active", step: clampStep(state.step + 1) };
}

export function retreatTour(state: OnboardingState): OnboardingState {
  if (isFinished(state)) {
    return state;
  }
  return { ...state, status: "active", step: clampStep(state.step - 1) };
}

export function selectGoal(state: OnboardingState, goal: GoalId): OnboardingState {
  return { ...state, goal };
}

export function finishTour(state: OnboardingState): OnboardingState {
  return { ...state, status: "done", step: LAST_STEP_INDEX };
}

export function skipTour(state: OnboardingState): OnboardingState {
  return { ...state, status: "skipped" };
}
