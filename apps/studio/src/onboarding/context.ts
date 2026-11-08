import { createContext, useContext } from "react";

import type { OnboardingState, SkipReason } from "./machine";

/**
 * The tour's public surface. Components outside the onboarding module only
 * ever need `enabled` (to show a replay entry) and `restart`.
 */
export interface OnboardingController {
  enabled: boolean;
  open: boolean;
  state: OnboardingState;
  advance: () => void;
  /** Advance past one scene without leaving the tour. */
  skipScene: () => void;
  back: () => void;
  complete: () => void;
  /** Leave the tour for good, recording why. */
  skip: (reason?: SkipReason) => void;
  /** Open the tour, resuming stored progress unless it is already finished. */
  openTour: () => void;
  /** Replay from the first scene. */
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
