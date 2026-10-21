import { createContext, useContext } from "react";

import type { GoalId } from "./content";
import type { OnboardingState } from "./machine";

/**
 * The wizard's public surface. Components outside the onboarding module only
 * ever need `enabled` (to show a replay entry) and `restart`.
 */
export interface OnboardingController {
  enabled: boolean;
  open: boolean;
  state: OnboardingState;
  chooseGoal: (goal: GoalId) => void;
  advance: () => void;
  back: () => void;
  complete: () => void;
  skip: () => void;
  restart: () => void;
}

export const OnboardingContext = createContext<OnboardingController | null>(null);

export function useOnboarding(): OnboardingController {
  const value = useContext(OnboardingContext);
  if (!value) {
    throw new Error("useOnboarding must be used within an OnboardingProvider");
  }
  return value;
}
