import { describe, expect, it } from "vitest";

import tokensCss from "./tokens.css?raw";
import themeCss from "./theme.css?raw";

/**
 * Colour and token guards for the theme.
 *
 * Contrast is measured here from the token values themselves rather than in
 * jsdom, which has no layout to resolve `var()` chains against. Any surface
 * regression that breaks a token shows up as a failing ratio instead of as
 * unreadable text in a screenshot nobody looked at.
 *
 * `tokens.css` is the palette; `theme.css` only consumes it. Reading the values
 * out of the token file is what keeps this gate honest — a colour declared in a
 * rule would be measured against nothing.
 */

function readBlock(source: string, selector: string): string {
  const start = source.indexOf(selector);
  expect(start, `missing ${selector} block`).toBeGreaterThanOrEqual(0);
  const open = source.indexOf("{", start);
  return source.slice(open + 1, source.indexOf("}", open));
}

function colorTokens(body: string): Record<string, string> {
  return Object.fromEntries(
    Array.from(body.matchAll(/--([a-z0-9-]+):\s*(#[0-9a-fA-F]{6})\s*;/g), (match) => [
      match[1],
      match[2],
    ]),
  );
}

/** The translucent overlays (`--surface-hover`) a token value can sit on. */
function overlayTokens(body: string): Record<string, [number, number, number, number]> {
  return Object.fromEntries(
    Array.from(
      body.matchAll(
        /--([a-z0-9-]+):\s*rgba\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*([0-9.]+)\s*\)\s*;/g,
      ),
      (match) => [match[1], [Number(match[2]), Number(match[3]), Number(match[4]), Number(match[5])]],
    ),
  );
}

const darkPalette = readBlock(tokensCss, ":root {");
const lightPalette = readBlock(tokensCss, "html.theme-light {");
const dark = colorTokens(darkPalette);
const light = { ...dark, ...colorTokens(lightPalette) };
const overlays = { dark: overlayTokens(darkPalette), light: overlayTokens(lightPalette) };

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

/**
 * What a translucent overlay paints over an opaque surface, as a hex.
 *
 * An `rgba()` token has no contrast of its own; the reader sees the composite. Alpha
 * compositing happens in the encoded channel, which is what `contrast()` then
 * linearizes.
 */
function composite(overlay: [number, number, number, number], base: string): string {
  const [r, g, b, a] = overlay;
  const [br, bg, bb] = Array.from(base.replace("#", "").matchAll(/../g), (pair) =>
    parseInt(pair[0], 16),
  );
  const mix = (top: number, bottom: number) => Math.round(a * top + (1 - a) * bottom);
  return `#${[mix(r, br), mix(g, bg), mix(b, bb)]
    .map((value) => value.toString(16).padStart(2, "0"))
    .join("")}`;
}

const TEXT_TOKENS = ["text", "muted", "faint", "accent", "green", "amber"];
const SURFACES = ["bg", "bg-raised"];
const CHART_HOOKS = ["chart-1", "chart-2", "chart-3", "chart-4", "chart-5", "chart-6"];

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

    it(`keeps the theme control's labels legible on the checked pill in the ${name} theme`, () => {
      // Settings draws an unlabelled radio pill: the unchecked label is `--muted`
      // on the raised surface, the checked one is `--text` on the raised surface
      // under `--surface-hover`. Both are body text, so both owe 4.5:1.
      const hovered = composite(overlays[name]["surface-hover"], tokens["bg-raised"]);
      const failures = (["muted", "text"] as const)
        .filter((token) => contrast(tokens[token], hovered) < 4.5)
        .map(
          (token) =>
            `--${token} ${tokens[token]} on --surface-hover over --bg-raised ${hovered}: ` +
            `${contrast(tokens[token], hovered).toFixed(2)}:1`,
        );
      expect(failures).toEqual([]);
    });

    it(`keeps every chart hook legible at 3:1 in the ${name} theme`, () => {
      // The hooks a chart draws with are graphics, not body text, so they owe
      // WCAG's 3:1 non-text minimum against both surfaces a chart sits on.
      const failures = CHART_HOOKS.flatMap((token) =>
        SURFACES.filter((surface) => contrast(tokens[token], tokens[surface]) < 3).map(
          (surface) =>
            `--${token} ${tokens[token]} on --${surface} ${tokens[surface]}: ${contrast(
              tokens[token],
              tokens[surface],
            ).toFixed(2)}:1`,
        ),
      );
      expect(failures).toEqual([]);
    });
  }
});

describe("the palette source", () => {
  it("is one file the theme imports", () => {
    expect(themeCss).toContain('@import "./tokens.css"');
  });

  it("declares each token once per palette, in the token file", () => {
    // A token redefined in `theme.css` is a palette decision made outside the
    // palette, and `theme.test.ts` cannot measure what it does not read.
    for (const name of [...TEXT_TOKENS, ...SURFACES, ...CHART_HOOKS]) {
      expect(
        new RegExp(`--${name}:\\s*#`).test(readBlock(tokensCss, ":root {")),
        `--${name} is not defined in the dark palette`,
      ).toBe(true);
      expect(
        new RegExp(`--${name}:\\s*#`).test(readBlock(tokensCss, "html.theme-light {")),
        `--${name} is not defined in the light palette`,
      ).toBe(true);
    }
  });
});

describe("theme tokens", () => {
  it("defines every custom property the stylesheet references without a fallback", () => {
    const referenced = new Set(
      Array.from(themeCss.matchAll(/var\(--([a-z0-9-]+)\s*\)/g), (match) => match[1]),
    );
    const definitions = `${tokensCss}\n${themeCss}`;
    const missing = Array.from(referenced).filter(
      (name) => !new RegExp(`--${name}:`).test(definitions),
    );
    expect(missing).toEqual([]);
  });
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
