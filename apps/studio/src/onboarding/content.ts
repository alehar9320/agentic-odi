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

export function sceneById(id: TourSceneId): TourScene {
  const scene = SCENES.find((entry) => entry.id === id);
  if (!scene) {
    throw new Error(`Unknown tour scene: ${id}`);
  }
  return scene;
}
