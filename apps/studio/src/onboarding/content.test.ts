import { describe, expect, it } from "vitest";

import { SCENES, SCENE_COUNT, sceneById } from "./content";

describe("tour scenes", () => {
  it("has exactly three scenes, in the order the work is done", () => {
    expect(SCENES.map((scene) => scene.id)).toEqual(["hear", "score", "place"]);
    expect(SCENE_COUNT).toBe(3);
  });

  it("gives every scene a label, a title, and a lead", () => {
    for (const scene of SCENES) {
      expect(scene.label.length).toBeGreaterThan(0);
      expect(scene.title.length).toBeGreaterThan(0);
      expect(scene.lead.length).toBeGreaterThan(0);
    }
  });

  it("resolves a scene by id and rejects an unknown one", () => {
    expect(sceneById("score").label).toBe("Score it");
    expect(() => sceneById("nope" as never)).toThrow(/Unknown tour scene/);
  });
});
