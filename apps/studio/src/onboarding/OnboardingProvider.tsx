import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";

import { isFeatureEnabled } from "../features/flags";
import { OnboardingContext, type OnboardingController } from "./context";
import type { GoalId } from "./content";
import {
  advanceTour,
  createOnboardingState,
  finishTour,
  isFinished,
  retreatTour,
  selectGoal,
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
  // The tour never opens by itself. The stage is the first impression; the
  // tour is an answer to "show me around", from the home stage or Settings.
  const [open, setOpen] = useState(false);

  // Persist every transition so closing the app mid-tour resumes where it left
  // off. A pending tour that was never opened is not a record worth writing.
  useEffect(() => {
    if (!featureEnabled || (!open && state.status === "pending")) {
      return;
    }
    writeOnboardingState(state);
  }, [featureEnabled, open, state]);

  const chooseGoal = useCallback((goal: GoalId) => {
    setState((prev) => selectGoal(prev, goal));
  }, []);

  const advance = useCallback(() => {
    setState(advanceTour);
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

  /** Open the tour where it was left, or from the top once it is finished. */
  const openTour = useCallback(() => {
    if (!featureEnabled) {
      return;
    }
    setState((prev) => (isFinished(prev) ? startTour(prev) : prev));
    setOpen(true);
  }, [featureEnabled]);

  /** Replay from the first step, forgetting the previous choice. */
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
      back,
      complete,
      skip,
      openTour,
      restart,
    }),
    [
      featureEnabled,
      open,
      state,
      chooseGoal,
      advance,
      back,
      complete,
      skip,
      openTour,
      restart,
    ],
  );

  return <OnboardingContext.Provider value={value}>{children}</OnboardingContext.Provider>;
}
