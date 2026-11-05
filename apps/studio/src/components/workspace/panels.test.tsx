import { describe, expect, it } from "vitest";

import { SURFACES, UNMEASURED_PANELS } from "../../../e2e/a11y/screens";
import { findPanel, SETTINGS_PANEL, WORKSPACE_PANELS } from "./panels";

describe("findPanel", () => {
  it("finds the records lens instead of falling back to settings", () => {
    // `findPanel` returns SETTINGS_PANEL for an id it does not know, so a lens
    // missing from the registry still renders — as the wrong panel. This is the
    // one assertion that catches that.
    expect(findPanel("records").id).toBe("records");
    expect(WORKSPACE_PANELS.some((panel) => panel.id === "records")).toBe(true);
  });

  it("finds the decision brief lens", () => {
    // The brief is reachable from `/brief` and from the landscape header, and
    // both routes land on the same document.
    expect(findPanel("brief").id).toBe("brief");
    expect(WORKSPACE_PANELS.some((panel) => panel.id === "brief")).toBe(true);
  });
});

/**
 * The contrast gate's surface list, held against the registry the app renders
 * from (ALH-216).
 *
 * `e2e/a11y.spec.ts` claims "every lens is measured in both palettes", and a
 * claim about a list is only as good as the guarantee that the list is the
 * whole set. A panel added here without a screen entry would render, ship, and
 * never be measured — which is exactly how the palette drifted the first time.
 */
describe("the a11y gate's surface list", () => {
  // `findPanel` falls back to settings, so the registry plus the settings
  // definition is the complete set of ids the app can paint.
  const registered: string[] = [
    ...WORKSPACE_PANELS.map((panel) => panel.id),
    SETTINGS_PANEL.id,
  ];

  it("walks every lens the workspace can open", () => {
    const measured = SURFACES.map((surface) => surface.panel);
    const recorded = UNMEASURED_PANELS.map((entry) => entry.panel);

    expect(
      registered
        .filter((id) => !measured.includes(id) && !recorded.includes(id))
        .sort(),
    ).toEqual([]);
  });

  it("names only real panels, in the list and in the excuses", () => {
    // The opposite failure: a screen entry pointing at an id that no longer
    // exists would measure nothing and still be counted as coverage.
    const dangling = [
      ...SURFACES.map((surface) => surface.panel),
      ...UNMEASURED_PANELS.map((entry) => entry.panel),
    ].filter((panel): panel is string => panel !== null && !registered.includes(panel));

    expect(dangling.sort()).toEqual([]);
  });

  it("records an owner and a reason for anything it cannot paint", () => {
    // "No browser can reach it" is only acceptable when the issue that will
    // change that is written down next to it.
    expect(
      UNMEASURED_PANELS.filter(
        (entry) => entry.issue.trim() === "" || entry.reason.trim() === "",
      ),
    ).toEqual([]);
    expect(new Set(UNMEASURED_PANELS.map((entry) => entry.panel)).size).toBe(
      UNMEASURED_PANELS.length,
    );
  });

  it("measures each panel once, and the home page with them", () => {
    const ids = SURFACES.map((surface) => surface.id);
    expect(new Set(ids).size).toBe(ids.length);
    expect(ids).toContain("home");
    const notALens = SURFACES.filter((surface) => surface.panel === null).map(
      (surface) => surface.id,
    );
    expect(notALens).toEqual(["home"]);
  });
});
