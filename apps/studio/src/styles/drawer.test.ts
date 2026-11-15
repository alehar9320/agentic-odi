/**
 * Guards for the drawer stylesheet (#736).
 *
 * The sheet is the drawer's alone. It must be loaded, it must not declare its
 * own palette, and a class renamed in a component must not lose its styling
 * silently — the same checks the mainstage sheet gets.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import drawerCss from "./drawer.css?raw";

// Vitest runs with the studio package as its working directory.
const theme = readFileSync(join(process.cwd(), "src/styles/theme.css"), "utf8");
const component = readFileSync(
  join(process.cwd(), "src/components/layout/NavigationDrawer.tsx"),
  "utf8",
);
const quickJump = readFileSync(
  join(process.cwd(), "src/components/layout/QuickJump.tsx"),
  "utf8",
);

function classesUsedIn(source: string, prefix: string): string[] {
  const names = new Set<string>();
  for (const match of source.matchAll(new RegExp(`\\b${prefix}[a-z0-9_-]*`, "g"))) {
    names.add(match[0]);
  }
  return [...names];
}

describe("drawer stylesheet", () => {
  it("is loaded once by the studio theme", () => {
    expect(theme).toContain('@import "./drawer.css"');
  });

  it("owns one breakpoint, matching the rest of the shell", () => {
    expect(drawerCss).toContain("@media (max-width: 1023px)");
  });

  it("never declares palette tokens of its own", () => {
    expect(drawerCss).not.toMatch(/:root\s*\{/);
  });

  it("defines a rule for every drawer class the component renders", () => {
    const used = classesUsedIn(component, "drawer__");
    expect(used.length).toBeGreaterThan(0);
    expect(used.filter((name) => !drawerCss.includes(`.${name}`))).toEqual([]);
  });

  it("defines a rule for every Quick jump class the sheet renders", () => {
    const used = classesUsedIn(quickJump, "quickjump__");
    expect(used.length).toBeGreaterThan(0);
    expect(used.filter((name) => !drawerCss.includes(`.${name}`))).toEqual([]);
    expect(drawerCss).toContain(".quickjump-overlay");
  });
});
