/**
 * The tour's scenes, as data.
 *
 * Three scenes on one sample brief, in the order a person rehearses the work:
 * hear a quote, score what it implies, see where it lands. The copy lives here
 * so the flow can be rewritten without touching a component.
 */

export type TourSceneId = "hear" | "score" | "place";

export interface TourScene {
  id: TourSceneId;
  /** Short label for the scene dots and the dialog's eyebrow. */
  label: string;
  title: string;
  lead: string;
}

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

export const SCENES: TourScene[] = [
  {
    id: "hear",
    label: "Hear it",
    title: "What is this person trying to get done?",
    lead:
      "A customer said something. The job is the progress they are after, which is not " +
      "the same as the words they used.",
  },
  {
    id: "score",
    label: "Score it",
    title: "Two numbers, one opportunity.",
    lead:
      "Importance and satisfaction are the only inputs. The score is a sorting device, " +
      "not a verdict.",
  },
  {
    id: "place",
    label: "Place it",
    title: "Where it lands.",
    lead: "One outcome beside the others, and the evidence the loop is still missing.",
  },
];

export const SCENE_COUNT = SCENES.length;

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

export function sceneById(id: TourSceneId): TourScene {
  const scene = SCENES.find((entry) => entry.id === id);
  if (!scene) {
    throw new Error(`Unknown tour scene: ${id}`);
  }
  return scene;
}
