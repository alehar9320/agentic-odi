/**
 * First-run onboarding for The Living Studio.
 *
 * The app only needs the provider and the wizard; everything else stays inside
 * this module. Replay is available through `useOnboarding` when the feature
 * flag is on.
 */
export { FirstRunWizard } from "./FirstRunWizard";
export { OnboardingProvider } from "./OnboardingProvider";
export { useOnboarding } from "./context";
