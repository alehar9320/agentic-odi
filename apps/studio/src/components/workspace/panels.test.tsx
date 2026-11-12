import { describe, expect, it } from "vitest";

import { findPanel, WORKSPACE_PANELS } from "./panels";

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
