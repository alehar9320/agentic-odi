import { describe, expect, it } from "vitest";

import themeCss from "./theme.css?raw";

/**
 * The display serif and the scalar foundation this issue lays.
 *
 * Every token here is additive: existing names keep working in both themes,
 * and this file is the contract that keeps them from drifting. The counts
 * are read from the stylesheet itself, so a later pass that migrates the
 * hard-coded font-size declarations to the scale updates this file too.
 */
describe("design tokens", () => {
  it("defines the display face", () => {
    expect(themeCss).toContain("--font-display");
    expect(themeCss).toMatch(/--font-display:\s*"[^"]*"/);
  });

  it("defines a type scale", () => {
    const scale = [
      "--text-2xs",
      "--text-xs",
      "--text-sm",
      "--text-base",
      "--text-md",
      "--text-lg",
      "--text-xl",
      "--text-2xl",
      "--text-3xl",
      "--text-4xl",
    ];
    for (const token of scale) {
      expect(themeCss).toMatch(
        new RegExp(`${token.replace(/[-]/g, "\\-")}:\\s*\\d`),
      );
    }
    // The scale is complete and in order: nothing between the smallest and
    // largest is missing, so a later pass cannot silently skip a size.
    const indices = scale.map((token) => themeCss.indexOf(token));
    for (let i = 1; i < indices.length; i++) {
      expect(indices[i]).toBeGreaterThan(indices[i - 1]);
    }
  });

  it("defines a spacing scale", () => {
    const spaces = ["--space-1", "--space-2", "--space-3", "--space-4", "--space-5", "--space-6", "--space-7", "--space-8"];
    for (const token of spaces) {
      expect(themeCss).toMatch(
        new RegExp(`${token.replace(/[-]/g, "\\-")}:\\s*\\d`),
      );
    }
  });

  it("defines a radius scale", () => {
    const radii = ["--radius-sm", "--radius-md", "--radius-lg", "--radius-pill"];
    for (const token of radii) {
      expect(themeCss).toMatch(
        new RegExp(`${token.replace(/[-]/g, "\\-")}:\\s*\\d`),
      );
    }
  });

  it("defines a line-height scale", () => {
    const leading = ["--leading-tight", "--leading-snug", "--leading-normal", "--leading-relaxed", "--leading-loose"];
    for (const token of leading) {
      expect(themeCss).toMatch(
        new RegExp(`${token.replace(/[-]/g, "\\-")}:\\s*[0-9.]+`),
      );
    }
  });
});

describe("display serif", () => {
  it("is self-hosted with a swap strategy", () => {
    expect(themeCss).toContain("@font-face");
    expect(themeCss).toMatch(/font-display:\s*swap/);
    expect(themeCss).toMatch(/url\("\/fonts\/eb-garamond-latin-wght-normal\.woff2"\)/);
    expect(themeCss).toMatch(/url\("\/fonts\/eb-garamond-latin-wght-italic\.woff2"\)/);
  });

  it("falls back to a system serif stack", () => {
    expect(themeCss).toMatch(/--font-display:.*Georgia/);
    expect(themeCss).toMatch(/--font-display:.*serif/);
  });

  it("is applied at the four display sites and only those", () => {
    const sites = [
      ".brand__wordmark",
      ".hero__line",
      ".lens__title",
      ".ui-stat__value",
    ];
    for (const selector of sites) {
      const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      // Anchor at a line start so a compound selector that merely *contains*
      // the simple one (`.brand--home:hover .brand__wordmark`) is not hit.
      const block = themeCss.match(
        new RegExp(`(^|\\n)${escaped}\\s*\\{[^}]*\\}`, "m"),
      );
      expect(block, `missing rule for ${selector}`).toBeTruthy();
      expect(block![0]).toContain("font-family: var(--font-display)");
    }
  });

  it("never overrides font in the light theme", () => {
    const light = themeCss.match(/html\.theme-light\s*\{[\s\S]*?\}/);
    expect(light, "the light theme block is missing").toBeTruthy();
    expect(light![0]).not.toMatch(/--font/);
  });

  it("leaves the monospace face alone", () => {
    expect(themeCss).toContain("--mono: ui-monospace");
    expect(themeCss).not.toMatch(/--mono:.*var\(--font-display\)/);
  });
});