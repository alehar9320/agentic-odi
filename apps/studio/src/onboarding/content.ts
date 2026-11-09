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

export type WizardStepId = "welcome" | "goal" | "readiness" | "land";

export interface OnboardingGoal {
  id: GoalId;
  title: string;
  blurb: string;
  destination: GoalDestination;
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
    id: "land",
    label: "Where it lands",
    title: "Where it lands.",
    lead:
      "The outcome you scored, on the landscape beside two others. Keep the sample " +
      "to poke at, or start your own job.",
  },
];

export const GOALS: OnboardingGoal[] = [
  {
    id: "have-opportunity",
    title: "I have one in mind",
    blurb: "Bring the opportunity you're already weighing. We'll make it precise.",
    destination: {
      kind: "chat",
      prompt:
        "I have an opportunity in mind. Ask me what it is, then help me sharpen it into something I can defend.",
    },
    icon: "spark",
  },
  {
    id: "boss-priority",
    title: "My boss handed me a priority",
    blurb: "Turn a top-down ask into something customers actually feel.",
    destination: {
      kind: "chat",
      prompt:
        "My boss handed me a priority. Help me turn it into a real customer opportunity, and tell me what evidence would prove it matters.",
    },
    icon: "bolt",
  },
  {
    id: "find-opportunity",
    title: "Help me find the next one",
    blurb: "Look across what you know and find the gap worth chasing.",
    destination: {
      kind: "chat",
      prompt:
        "I need to find the next opportunity worth chasing. Help me look across what I know about my customers and find the gap that matters most.",
    },
    icon: "compass",
  },
  {
    id: "pressure-test",
    title: "Pressure-test a bet",
    blurb: "Put the bet on the table before you spend a sprint on it.",
    destination: {
      kind: "chat",
      prompt:
        "I have a bet I'm about to make. Pressure-test it with me: ask what it is, then tell me what would have to be true and what evidence I'm missing.",
    },
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
