import { describe, expect, it } from "vitest";

import { buildPaletteItems, matchPaletteItems, paletteItemsFor, type PaletteItem } from "./palette";

describe("buildPaletteItems", () => {
  it("includes every slash command in declared order", () => {
    const items = buildPaletteItems();
    const commands = items.filter((item) => item.group === "commands");
    expect(commands.map((item) => item.id)).toEqual([
      "help", "start", "new", "home", "jobs", "dashboard", "landscape", "jobmap",
      "segments", "brief", "impact", "evidence", "records", "capture", "settings", "status",
    ]);
  });

  it("appends every workspace panel in declared order after commands", () => {
    const items = buildPaletteItems();
    const panels = items.filter((item) => item.group === "panels");
    expect(panels.map((item) => item.id)).toEqual([
      "dashboard", "records", "catchup", "landscape", "brief", "jobmap", "segments",
      "evidence", "memory", "schedule", "capture", "settings",
    ]);
    expect(panels.every((item) => item.category === "Panels")).toBe(true);
  });

  it("assigns stable indexes within each group", () => {
    const items = buildPaletteItems();
    expect(items[0].index).toBe(0);
    expect(items[0].group).toBe("commands");
    const firstPanel = items.find((item) => item.group === "panels");
    expect(firstPanel?.index).toBe(0);
  });
});

describe("paletteItemsFor / matchPaletteItems ranking", () => {
  it("returns no items for an empty query", () => {
    expect(paletteItemsFor("")).toEqual([]);
    expect(paletteItemsFor("   ")).toEqual([]);
  });

  it("ranks an exact name match first", () => {
    const items = paletteItemsFor("help");
    expect(items[0].id).toBe("help");
    expect(items[0].name).toBe("/help");
  });

  it("ranks prefix matches before substring matches", () => {
    const items = paletteItemsFor("rec");
    // "/records" command outranks the "records" panel (group order), both are prefix matches.
    expect(items.map((item) => item.id)).toEqual(["records", "records"]);
    expect(items[0].group).toBe("commands");
    expect(items[1].group).toBe("panels");
    const bySubstring = paletteItemsFor("scores");
    expect(bySubstring.map((item) => item.id)).toContain("landscape");
  });

  it("matches case-insensitively", () => {
    const lower = paletteItemsFor("HELP");
    const upper = paletteItemsFor("help");
    expect(lower.map((item) => item.id)).toEqual(upper.map((item) => item.id));
  });

  it("trims whitespace around the query", () => {
    const spaced = paletteItemsFor("  help  ");
    expect(spaced.map((item) => item.id)).toEqual(["help"]);
  });

  it("breaks ties by group order then registry order", () => {
    // "dashboard" exists as both a command and a panel; command ranks first.
    const items = paletteItemsFor("dashboard");
    expect(items[0].id).toBe("dashboard");
    expect(items[0].group).toBe("commands");
    const panel = items.find((item) => item.group === "panels");
    expect(panel?.id).toBe("dashboard");
  });

  it("returns no items when nothing matches", () => {
    expect(paletteItemsFor("zzznomatch")).toEqual([]);
  });
});

describe("matchPaletteItems disabled contract", () => {
  it("keeps disabled items tagged with their reason instead of dropping them", () => {
    const items: PaletteItem[] = [
      {
        id: "help",
        name: "/help",
        label: "Help",
        description: "Every command.",
        category: "Start",
        group: "commands",
        index: 0,
      },
      {
        id: "locked",
        name: "/locked",
        label: "Locked",
        description: "Unavailable right now.",
        category: "Start",
        group: "commands",
        index: 1,
        disabled: true,
        disabledReason: "feature flag off",
      },
    ];
    const matched = matchPaletteItems(items, "locked");
    expect(matched).toHaveLength(1);
    expect(matched[0].disabled).toBe(true);
    expect(matched[0].disabledReason).toBe("feature flag off");
  });
});
