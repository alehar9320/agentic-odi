import { describe, expect, it } from "vitest";

import themeCss from "./theme.css?raw";

/**
 * The motion budget, asserted against the stylesheet itself.
 *
 * The house pattern (see `print.test.ts`) reads the CSS as raw text: jsdom has
 * no layout, so the only place a new inline duration can be caught is here.
 * A contributor who adds `transition: 0.33s` to theme.css fails this file
 * rather than shipping a number nobody chose.
 */

/** The `:root` token block, up to its closing brace. */
function tokenBlock(): string {
  const start = themeCss.indexOf(":root {");
  expect(start, "missing :root block").toBeGreaterThanOrEqual(0);
  return themeCss.slice(start, themeCss.indexOf("}", start));
}

/** Everything after the token block, where durations must be tokens. */
function rulesAfterTokens(): string {
  const start = themeCss.indexOf(":root {");
  const end = themeCss.indexOf("}", start);
  return themeCss.slice(end);
}

const DURATION_TOKEN = /--motion-(instant|fast|base|slow|loop):\s*(\d+ms|0)\s*;/g;
const ALLOWED_LOOPS = ["dot-pulse", "caret-blink"];

describe("motion scale", () => {
  it("defines the five duration tokens in :root", () => {
    const names = Array.from(tokenBlock().matchAll(DURATION_TOKEN), (m) => m[1]);
    expect(new Set(names)).toEqual(
      new Set(["instant", "fast", "base", "slow", "loop"]),
    );
  });

  it("keeps the easing helpers in the token block, not a second :root", () => {
    expect(tokenBlock()).toContain("--ease-out:");
    expect(tokenBlock()).toContain("--ease-spring:");
    expect(tokenBlock()).toContain("--ease-in-out:");
    // Exactly one :root block owns the motion values.
    expect(themeCss.match(/^:root \{/gm) ?? []).toHaveLength(1);
  });

  it("uses a token for every duration outside the token block", () => {
    // Token declarations are the only place a raw value may appear; drop them
    // (including the reduced-motion overrides) before scanning for literals.
    const body = rulesAfterTokens().replace(/--[\w-]+:\s*[\d.]+m?s\s*;/g, "");
    const literals = Array.from(
      body.matchAll(/(?<![\w-])(\d+(?:\.\d+)?)(ms|s)\b/g),
      (m) => m[0],
    );
    expect(literals, `raw durations found: ${literals.join(", ")}`).toEqual([]);
  });

  it("declares reduced motion once, at the token layer", () => {
    expect(themeCss.match(/prefers-reduced-motion/g) ?? []).toHaveLength(1);
    const block = themeCss.slice(
      themeCss.indexOf("@media (prefers-reduced-motion: reduce)"),
    );
    for (const name of ["fast", "base", "slow", "loop"]) {
      expect(block).toContain(`--motion-${name}: 0ms;`);
    }
  });

  it("loops nothing but the two functional indicators", () => {
    const loops = Array.from(
      themeCss.matchAll(/animation:\s*([\w-]+)[^;]*infinite/g),
      (m) => m[1],
    );
    expect(new Set(loops)).toEqual(new Set(ALLOWED_LOOPS));
  });
});
