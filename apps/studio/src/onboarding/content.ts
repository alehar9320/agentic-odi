/**
 * The tour's copy and structure live here so the flow can be rewritten without
 * touching a component. Adding a scene is a data edit.
 *
 * The tour no longer describes the product; it rehearses the ODI loop on one
 * labelled sample brief: hear a quote, score what it implies, see where it
 * lands. The scenes' interactive content is #594 and #595; this slice ships the
 * machine, the sample, and the shell.
 */

export type SceneId = "hear" | "score" | "place";

export interface TourScene {
  id: SceneId;
  /** The wordmark shown in the dialog header. */
  label: string;
  title: string;
  lead: string;
}

export const SCENES: TourScene[] = [
  {
    id: "hear",
    label: "Hear it",
    title: "Hear it in a customer's words.",
    lead:
      "This is one sample brief, not your work. Read the quote, then say what " +
      "the speaker is really trying to get done.",
  },
  {
    id: "score",
    label: "Score it",
    title: "Turn the quote into a scored outcome.",
    lead:
      "An outcome is a measurable need. Importance and satisfaction decide " +
      "whether the market is underserved.",
  },
  {
    id: "place",
    label: "Place it",
    title: "See where the outcome lands.",
    lead:
      "A score only matters beside the others. Here is where this one sits, and " +
      "what evidence is still missing.",
  },
];

export const SCENE_COUNT = SCENES.length;

export function sceneById(id: SceneId): TourScene {
  return SCENES.find((scene) => scene.id === id) ?? SCENES[0];
}
