import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";

import { isFeatureEnabled } from "../features/flags";
import { OnboardingContext, type OnboardingController } from "./context";
import type { GoalId } from "./content";
import {
  advanceTour,
  createOnboardingState,
  finishTour,
  retreatTour,
  selectGoal,
  shouldAutoOpen,
  skipStepTour,
  skipTour,
  startTour,
  type OnboardingState,
} from "./machine";
import { readOnboardingState, writeOnboardingState } from "./storage";

export interface OnboardingProviderProps {
  children: ReactNode;
  /** Override for tests and stories; defaults to the `firstRunWizard` flag. */
  enabled?: boolean;
}

export function OnboardingProvider({ children, enabled }: OnboardingProviderProps) {
  const featureEnabled = enabled ?? isFeatureEnabled("firstRunWizard");

  const [state, setState] = useState<OnboardingState>(
    () => readOnboardingState() ?? createOnboardingState(),
  );
  const [open, setOpen] = useState<boolean>(() => featureEnabled && shouldAutoOpen(state));

  // Persist every transition so closing the app mid-tour resumes where it left off.
  useEffect(() => {
    if (featureEnabled) {
      writeOnboardingState(state);
    }
  }, [featureEnabled, state]);

  const chooseGoal = useCallback((goal: GoalId) => {
    setState((prev) => selectGoal(prev, goal));
  }, []);

  const advance = useCallback(() => {
    setState(advanceTour);
  }, []);

  const skipStep = useCallback(() => {
    setState(skipStepTour);
  }, []);

  const back = useCallback(() => {
    setState(retreatTour);
  }, []);

  const complete = useCallback(() => {
    setState(finishTour);
    setOpen(false);
  }, []);

  const skip = useCallback(() => {
    setState(skipTour);
    setOpen(false);
  }, []);

  const restart = useCallback(() => {
    if (!featureEnabled) {
      return;
    }
    setState(startTour);
    setOpen(true);
  }, [featureEnabled]);

  const value = useMemo<OnboardingController>(
    () => ({
      enabled: featureEnabled,
      open,
      state,
      chooseGoal,
      advance,
      skipStep,
      back,
      complete,
      skip,
      restart,
    }),
    [
      featureEnabled,
      open,
      state,
      chooseGoal,
      advance,
      skipStep,
      back,
      complete,
      skip,
      restart,
    ],
  );

  return <OnboardingContext.Provider value={value}>{children}</OnboardingContext.Provider>;
}
