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

describe("reduced transparency", () => {
  it("drops every blur and goes opaque", () => {
    const start = themeCss.indexOf("@media (prefers-reduced-transparency: reduce)");
    expect(start, "missing the reduced-transparency block").toBeGreaterThanOrEqual(0);
    const block = themeCss.slice(start, start + 1400);
    for (const selector of [
      ".scrim",
      ".bar",
      ".outcome-card",
      ".settings-drawer",
      ".banner",
      ".changelog-modal",
      ".changelog-overlay",
      ".diagnostics-overlay",
      ".suggestion-modal",
      ".catchup-summary",
      ".studio-metric",
    ]) {
      expect(block, `${selector} keeps its blur`).toContain(selector);
    }
    expect(block).toContain("backdrop-filter: none");
    expect(block).toContain("background-color: var(--bg-raised)");
  });
});

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

describe("more contrast", () => {
  it("promotes muted and faint past AAA and thickens hairlines", () => {
    const start = themeCss.indexOf("@media (prefers-contrast: more)");
    expect(start, "missing the more-contrast block").toBeGreaterThanOrEqual(0);
    const block = themeCss.slice(start, start + 1400);
    const promoted = {
      dark: { muted: "#c6cad3", faint: "#adb2bf" },
      light: { muted: "#3a4050", faint: "#454c5c" },
    };
    for (const [name, tokens] of [
      ["dark", promoted.dark],
      ["light", promoted.light],
    ] as const) {
      const background = name === "dark" ? dark.bg : light.bg;
      for (const [token, value] of Object.entries(tokens)) {
        expect(block, `${name} --${token} is not promoted`).toContain(`--${token}: ${value}`);
        expect(contrast(value, background), `${name} --${token} on --bg`).toBeGreaterThanOrEqual(7);
      }
    }
    expect(block).toContain("border-width: 1.5px");
  });
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

describe("theme change", () => {
  it("cross-fades only through the fading class", () => {
    expect(themeCss).toMatch(
      /html\.theme-fading[^{]*\{[^}]*transition-duration:\s*120ms/,
    );
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

describe("selection and caret", () => {
  it("carries the accent into selection and the caret", () => {
    expect(themeCss).toMatch(
      /::selection\s*\{[^}]*background:\s*color-mix\(in srgb,\s*var\(--accent\)/,
    );
    expect(themeCss).toMatch(/caret-color:\s*var\(--accent\)/);
  });
});
