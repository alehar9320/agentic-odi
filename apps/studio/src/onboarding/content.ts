import type { WorkspacePanelId } from "../types";

/**
 * The tour's copy and structure live here so the flow can be rewritten without
 * touching a component. Adding a goal is a data edit.
 */

export type GoalId = "name-job" | "landscape" | "impact" | "capture";

export type GoalDestination =
  | { kind: "setup" }
  | { kind: "panel"; panel: WorkspacePanelId };

export type GoalIconName = "job" | "landscape" | "impact" | "capture";

export type WizardStepId = "welcome" | "goal" | "readiness" | "launch";

export interface OnboardingGoal {
  id: GoalId;
  title: string;
  blurb: string;
  /** What the user walks away with, shown on the final step. */
  result: string;
  destination: GoalDestination;
  /** How the final step describes where the choice leads. */
  destinationLabel: string;
  /** The final-step action. */
  cta: string;
  icon: GoalIconName;
}

export interface OnboardingStep {
  id: WizardStepId;
  label: string;
  title: string;
  lead: string;
}

export const STEPS: OnboardingStep[] = [
  {
    id: "welcome",
    label: "Welcome",
    title: "People don't buy products.",
    lead:
      "They hire them to get a job done. The Living Studio helps you name that job, " +
      "measure how badly it is served, and test the bet before you build.",
  },
  {
    id: "goal",
    label: "Starting point",
    title: "Where do you want to begin?",
    lead: "One starting point. Everything else stays one click away in the sidebar.",
  },
  {
    id: "readiness",
    label: "Instruments",
    title: "A quick look at your instruments.",
    lead:
      "The studio runs locally. The copilot needs an OpenAI-compatible model to " +
      "answer; everything else works by hand.",
  },
  {
    id: "launch",
    label: "First move",
    title: "Your first move.",
    lead: "Nothing changes until you choose.",
  },
];

export const GOALS: OnboardingGoal[] = [
  {
    id: "name-job",
    title: "Name the job",
    blurb: "Answer four quick questions about your product, customer, and job.",
    result: "A saved brief and a job at the center of the map.",
    destination: { kind: "setup" },
    destinationLabel: "The studio will ask four quick questions, then build your job map.",
    cta: "Set up my context",
    icon: "job",
  },
  {
    id: "landscape",
    title: "Read the landscape",
    blurb: "See every outcome scored. Anything above 10 is underserved.",
    result: "The opportunity landscape, sorted by where the gaps are.",
    destination: { kind: "panel", panel: "landscape" },
    destinationLabel: "The opportunity landscape opens full-screen.",
    cta: "Open the landscape",
    icon: "landscape",
  },
  {
    id: "impact",
    title: "Simulate a bet",
    blurb: "Preview the friction collapse before you spend a sprint.",
    result: "A before-and-after impact simulation for one bet.",
    destination: { kind: "panel", panel: "impact" },
    destinationLabel: "The impact simulator opens full-screen.",
    cta: "Open impact",
    icon: "impact",
  },
  {
    id: "capture",
    title: "Capture an outcome",
    blurb: "Type one outcome and score it by hand. No model needed.",
    result: "One scored outcome on the canvas.",
    destination: { kind: "panel", panel: "capture" },
    destinationLabel: "A focused form that writes straight to the MCP repository.",
    cta: "Capture an outcome",
    icon: "capture",
  },
];

export const GOAL_STEP_INDEX = STEPS.findIndex((step) => step.id === "goal");

export function goalById(id: GoalId | null): OnboardingGoal | null {
  if (!id) {
    return null;
  }
  return GOALS.find((goal) => goal.id === id) ?? null;
}
