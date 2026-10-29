import type { WorkspacePanelId } from "../types";

/**
 * The tour's copy and structure live here so the flow can be rewritten without
 * touching a component. Adding a goal is a data edit.
 */

export type GoalId =
  | "have-opportunity"
  | "boss-priority"
  | "find-opportunity"
  | "pressure-test";

export type GoalDestination =
  | { kind: "setup" }
  | { kind: "panel"; panel: WorkspacePanelId }
  | { kind: "chat"; prompt: string };

export type GoalIconName = "spark" | "bolt" | "compass" | "signal";

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
    title: "What do you want to win?",
    lead:
      "You already have a sense of the opportunity. The studio helps you test it — " +
      "against customers, the business, and what you can actually do next.",
  },
  {
    id: "goal",
    label: "Starting point",
    title: "What's on your mind?",
    lead: "Pick the one that sounds like your week. You can change direction any time by saying so.",
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
    lead: "One sentence is enough to start.",
  },
];

export const GOALS: OnboardingGoal[] = [
  {
    id: "have-opportunity",
    title: "I have one in mind",
    blurb: "Bring the opportunity you're already weighing. We'll make it precise.",
    result: "A plain-language thesis and the smallest next move.",
    destination: {
      kind: "chat",
      prompt:
        "I have an opportunity in mind. Ask me what it is, then help me sharpen it into something I can defend.",
    },
    destinationLabel: "We start in the conversation. Tell me what you're seeing.",
    cta: "Sharpen my opportunity",
    icon: "spark",
  },
  {
    id: "boss-priority",
    title: "My boss handed me a priority",
    blurb: "Turn a top-down ask into something customers actually feel.",
    result: "A customer-grounded thesis and the first question to ask.",
    destination: {
      kind: "chat",
      prompt:
        "My boss handed me a priority. Help me turn it into a real customer opportunity, and tell me what evidence would prove it matters.",
    },
    destinationLabel: "We start in the conversation. Tell me what you were asked for.",
    cta: "Make it real",
    icon: "bolt",
  },
  {
    id: "find-opportunity",
    title: "Help me find the next one",
    blurb: "Look across what you know and find the gap worth chasing.",
    result: "A ranked landscape and one place to start.",
    destination: {
      kind: "chat",
      prompt:
        "I need to find the next opportunity worth chasing. Help me look across what I know about my customers and find the gap that matters most.",
    },
    destinationLabel: "We start in the conversation. Tell me what you already know.",
    cta: "Find my next opportunity",
    icon: "compass",
  },
  {
    id: "pressure-test",
    title: "Pressure-test a bet",
    blurb: "Put the bet on the table before you spend a sprint on it.",
    result: "A clear read on whether it holds — and what would change your mind.",
    destination: {
      kind: "chat",
      prompt:
        "I have a bet I'm about to make. Pressure-test it with me: ask what it is, then tell me what would have to be true and what evidence I'm missing.",
    },
    destinationLabel: "We start in the conversation. Tell me the bet you're weighing.",
    cta: "Pressure-test my bet",
    icon: "signal",
  },
];

export const GOAL_STEP_INDEX = STEPS.findIndex((step) => step.id === "goal");

export function goalById(id: GoalId | null): OnboardingGoal | null {
  if (!id) {
    return null;
  }
  return GOALS.find((goal) => goal.id === id) ?? null;
}
