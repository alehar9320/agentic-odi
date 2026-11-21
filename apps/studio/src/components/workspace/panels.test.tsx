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

  it("gives each destination one plain name, shared by the rail header and the palette", () => {
    const labels = Object.fromEntries(WORKSPACE_PANELS.map((panel) => [panel.id, panel.label]));

    expect(labels.landscape).toBe("Where to focus");
    expect(labels.jobmap).toBe("Steps in the job");
    expect(labels.segments).toBe("Who this is for");
    expect(labels.evidence).toBe("What customers said");
    expect(labels.catchup).toBe("What changed");
    expect(labels.capture).toBe("Add what you heard");

    // The lens header reads the same words as the chip that opened it.
    for (const id of ["landscape", "jobmap", "segments", "evidence", "catchup", "capture"]) {
      const panel = WORKSPACE_PANELS.find((entry) => entry.id === id);
      expect(panel).toBeDefined();
      expect(panel?.title).toBe(panel?.label);
    }
  });

  it("finds the decision brief lens", () => {
    // The brief is reachable from `/brief` and from the landscape header, and
    // both routes land on the same document.
    expect(findPanel("brief").id).toBe("brief");
    expect(WORKSPACE_PANELS.some((panel) => panel.id === "brief")).toBe(true);
  });
});
