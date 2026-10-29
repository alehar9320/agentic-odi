/**
 * The optional product tour for The Living Studio.
 *
 * Nothing here opens by itself: the home stage and Settings ask the provider
 * for it. The app needs only the provider and the wizard; everything else stays
 * inside this module.
 */
export { FirstRunWizard } from "./FirstRunWizard";
export { OnboardingProvider } from "./OnboardingProvider";
export { useOnboarding } from "./context";
