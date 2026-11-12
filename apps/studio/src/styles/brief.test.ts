/**
 * Guards for the brief lens stylesheet.
 *
 * A lens stylesheet that is never imported styles nothing, and a class renamed
 * in the component but not in the CSS loses its styling silently — worse here
 * than elsewhere, because `print.css` selects the same names to keep them off
 * the page. Both failures are invisible in a unit test of the component, so
 * they are checked against the source text.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import briefCss from "./brief.css?raw";

// Vitest runs with the studio package as its working directory.
const entry = readFileSync(join(process.cwd(), "src/main.tsx"), "utf8");
const lens = readFileSync(join(process.cwd(), "src/components/brief/BriefLens.tsx"), "utf8");

describe("brief stylesheet", () => {
  it("is loaded by the studio entry", () => {
    expect(entry).toContain('"./styles/brief.css"');
  });

  it("defines a rule for every class the lens renders", () => {
    const used = Array.from(new Set(Array.from(lens.matchAll(/\bbrief(?:__[a-z-]+)?\b/g), (m) => m[0])));
    expect(used.length).toBeGreaterThan(0);
    expect(used.filter((name) => !briefCss.includes(`.${name}`))).toEqual([]);
  });
});
