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

const TEXT_TOKENS = ["text", "muted", "faint", "accent", "green", "amber"];
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
});
