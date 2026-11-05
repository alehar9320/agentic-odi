import { describe, expect, it } from "vitest";

import themeCss from "./theme.css?raw";

/**
 * Colour and token guards for the theme.
 *
 * Contrast is measured here from the token values themselves rather than in
 * jsdom, which has no layout to resolve `var()` chains against. Any surface
 * regression that breaks a token shows up as a failing ratio instead of as
 * unreadable text in a screenshot nobody looked at.
 */

function readBlock(selector: string): string {
  const start = themeCss.indexOf(selector);
  expect(start, `missing ${selector} block`).toBeGreaterThanOrEqual(0);
  const open = themeCss.indexOf("{", start);
  return themeCss.slice(open + 1, themeCss.indexOf("}", open));
}

function colorTokens(body: string): Record<string, string> {
  return Object.fromEntries(
    Array.from(body.matchAll(/--([a-z0-9-]+):\s*(#[0-9a-fA-F]{6})\s*;/g), (match) => [
      match[1],
      match[2],
    ]),
  );
}

const dark = colorTokens(readBlock(":root {"));
const light = { ...dark, ...colorTokens(readBlock("html.theme-light")) };

function channels(hex: string): number[] {
  return Array.from(hex.replace("#", "").matchAll(/../g), (pair) => {
    const value = parseInt(pair[0], 16) / 255;
    return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
  });
}

function luminance(hex: string): number {
  const [r, g, b] = channels(hex);
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function contrast(foreground: string, background: string): number {
  const [lighter, darker] = [luminance(foreground), luminance(background)].sort((a, b) => b - a);
  return (lighter + 0.05) / (darker + 0.05);
}

const TEXT_TOKENS = ["text", "muted", "faint", "accent", "green", "amber", "red"];
const SURFACES = ["bg", "bg-raised"];

describe("theme contrast", () => {
  for (const [name, tokens] of [
    ["dark", dark],
    ["light", light],
  ] as const) {
    it(`keeps every text token at WCAG AA (4.5:1) in the ${name} theme`, () => {
      const failures = TEXT_TOKENS.flatMap((token) =>
        SURFACES.filter((surface) => contrast(tokens[token], tokens[surface]) < 4.5).map(
          (surface) =>
            `--${token} ${tokens[token]} on --${surface} ${tokens[surface]}: ${contrast(
              tokens[token],
              tokens[surface],
            ).toFixed(2)}:1`,
        ),
      );
      expect(failures).toEqual([]);
    });

    it(`keeps the focus ring visible at 3:1 in the ${name} theme`, () => {
      const failures = SURFACES.filter((surface) => contrast(tokens.accent, tokens[surface]) < 3);
      expect(failures).toEqual([]);
    });
  }
});

describe("theme tokens", () => {
  it("defines every custom property the stylesheet references without a fallback", () => {
    const referenced = new Set(
      Array.from(themeCss.matchAll(/var\(--([a-z0-9-]+)\s*\)/g), (match) => match[1]),
    );
    const missing = Array.from(referenced).filter(
      (name) => !new RegExp(`--${name}:`).test(themeCss),
    );
    expect(missing).toEqual([]);
  });

  /**
   * The value a top-level rule declares for a property, read out of the file.
   *
   * The leading newline in each selector pins the lookup to the rule itself: a
   * media query may restate the selector to change only its size.
   */
  function declaration(selector: string, property: string): string | undefined {
    const body = readBlock(selector);
    return new RegExp(`\\n\\s*${property}:\\s*([^;]+);`).exec(body)?.[1].trim();
  }

  it("paints a notice, an evidence quote and a neutral meter from the palette, not from a stray hex", () => {
    expect(declaration("\n.notice {", "color")).toBe("var(--amber)");
    expect(declaration("\n.ui-card__evidence {", "color")).toBe("var(--text)");
    expect(declaration("\n.ui-tone-bg--neutral {", "background")).toBe("var(--faint)");
    expect(declaration("\n.brand__mark {", "background")).toBe("var(--brand-tile)");
    // The send disc used to be painted with the page's own ink, which in the
    // light theme meant ink on ink.
    expect(declaration("\n.composer__send {", "background")).toBe("var(--accent-fill)");
    expect(declaration("\n.composer__send {", "color")).toBe("var(--on-accent)");
  });

  it("never puts the filled control's ink on a ground it is not legible on", () => {
    // `--on-accent` is measured against `--accent-fill` and nothing else, so a
    // rule that reads one without the other is the defect the pair exists to
    // close: white ink on a brand colour chosen by a different theme.
    const lonely = themeCss
      .split("}")
      .map((rule) => rule.slice(rule.lastIndexOf("{") + 1))
      .filter(
        (body) =>
          /(^|\n)\s*color:\s*var\(--on-accent\)\s*;/.test(body) &&
          !body.includes("var(--accent-fill)"),
      )
      .map((body) => body.trim().split("\n")[0]);
    expect(lonely).toEqual([]);
  });

  it("makes an unknown status a shape, not only a colour", () => {
    const body = readBlock("\n.status-dot.is-unknown {");
    expect(body).toMatch(/background:\s*transparent/);
    expect(body).toMatch(/border-radius:\s*2px/);
    expect(body).toMatch(/box-shadow:\s*inset 0 0 0 1\.5px var\(--faint\)/);
    // Two box-shadows in one rule and the later one wins: the ring would vanish.
    expect(body).not.toMatch(/box-shadow:\s*none/);
  });
});

describe("role tokens", () => {
  /** Every custom property a block declares, alpha values included. */
  function declaredNames(block: string): Set<string> {
    return new Set(Array.from(block.matchAll(/--([a-z0-9-]+)\s*:/g), (match) => match[1]));
  }

  const darkNames = declaredNames(readBlock(":root {"));
  const lightBody = readBlock("html.theme-light");
  const lightNames = declaredNames(lightBody);

  it("defines every role the canvas and the filled controls read", () => {
    const roles = [
      "accent-fill",
      "on-accent",
      "plot-surface",
      "tint-accent",
      "tint-accent-strong",
      "tint-amber",
      "brand-tile",
    ];
    expect(roles.filter((name) => !darkNames.has(name))).toEqual([]);
  });

  it("overrides each role that changes with the theme, in the same block as the palette", () => {
    const themed = [
      "plot-surface",
      "tint-accent",
      "tint-accent-strong",
      "tint-amber",
    ];
    expect(themed.filter((name) => !lightNames.has(name))).toEqual([]);
    // The filled control is the one role that is brand rather than surface, so
    // both palettes read the same declaration. If a future light theme wants
    // its own fill, it must carry its own ink with it: the pair is what the
    // contrast test below measures, and it passes here only as a pair.
    expect([...lightNames].filter((name) => name === "accent-fill" || name === "on-accent")).toEqual([]);
    // The mascot's tile is brand, not a surface: declared once, in both palettes.
    expect(lightNames.has("brand-tile")).toBe(false);
  });

  for (const [name, tokens] of [
    ["dark", dark],
    ["light", light],
  ] as const) {
    it(`keeps the ink on a filled control at WCAG AA in the ${name} theme`, () => {
      const ratio = contrast(tokens["on-accent"], tokens["accent-fill"]);
      expect(ratio, `${tokens["on-accent"]} on ${tokens["accent-fill"]}`).toBeGreaterThanOrEqual(4.5);
    });

    it(`measures the canvas text on the ground the canvas paints, in the ${name} theme`, () => {
      const failures = ["text", "muted"]
        .map((token) => [token, contrast(tokens[token], tokens["plot-surface"])] as const)
        .filter(([, ratio]) => ratio < 4.5)
        .map(([token, ratio]) => `--${token} on --plot-surface: ${ratio.toFixed(2)}:1`);
      expect(failures).toEqual([]);
    });
  }
});

describe("composer focus ring", () => {
  it("follows the capsule's shape instead of floating inside it", () => {
    expect(themeCss).toMatch(
      /\.composer__shell:has\(\.composer__input:focus-visible\)\s*\{[^}]*outline:\s*2px solid var\(--accent\)/,
    );
    // Only the rectangular inline editor keeps a ring on the textarea itself.
    expect(themeCss).not.toMatch(/^\.composer__input:focus-visible,/m);
    expect(themeCss).toMatch(
      /\.composer--edit \.composer__input:focus-visible\s*\{[^}]*outline-offset:\s*2px/,
    );
  });
});
