import { describe, expect, it } from "vitest";

import themeCss from "./theme.css?raw";

/**
 * The typographic and scalar foundation, asserted from the stylesheet source
 * the same way print.test.ts asserts the print rules. These tokens are
 * additive: no existing rule changes meaning, and the light theme must never
 * carry a font override, so type cannot diverge between themes.
 */

function rootBlock(): string {
  const start = themeCss.indexOf(":root {");
  expect(start, "missing the :root block").toBeGreaterThanOrEqual(0);
  const open = themeCss.indexOf("{", start);
  return themeCss.slice(open + 1, themeCss.indexOf("\n}", open));
}

function lightBlock(): string {
  const start = themeCss.indexOf("html.theme-light {");
  expect(start, "missing the html.theme-light block").toBeGreaterThanOrEqual(0);
  const open = themeCss.indexOf("{", start);
  return themeCss.slice(open + 1, themeCss.indexOf("\n}", open));
}

const root = rootBlock();
const light = lightBlock();

describe("type and scalar tokens", () => {
  it("defines a display face with a system-serif fallback", () => {
    expect(root).toMatch(/--font-display:\s*"Source Serif 4",\s*Georgia/);
    expect(root).toMatch(/serif\s*;/);
  });

  it("defines at least five steps of a type scale", () => {
    const sizes = root.match(/--text-[a-z0-9]+:\s*[\d.]+rem/g) ?? [];
    expect(sizes.length).toBeGreaterThanOrEqual(5);
  });

  it("defines at least five steps of a spacing scale", () => {
    const spaces = root.match(/--space-\d+:\s*\d+px/g) ?? [];
    expect(spaces.length).toBeGreaterThanOrEqual(5);
  });

  it("defines a corner scale", () => {
    for (const token of ["--radius-sm", "--radius-md", "--radius-lg", "--radius-pill"]) {
      expect(root, `missing ${token}`).toContain(`${token}:`);
    }
  });

  it("defines a leading scale", () => {
    const leadings = root.match(/--leading-[a-z]+:\s*[\d.]+/g) ?? [];
    expect(leadings.length).toBeGreaterThanOrEqual(3);
  });

  it("keeps the existing tokens working unchanged", () => {
    expect(root).toContain("--font:");
    expect(root).toContain("--mono:");
  });
});

describe("the light theme stays colour-only", () => {
  it("carries no --font declaration, so type cannot diverge between themes", () => {
    expect(light).not.toMatch(/--font/);
  });
});

describe("the display face is self-hosted", () => {
  it("declares @font-face for the display family with font-display: swap", () => {
    expect(themeCss).toMatch(/@font-face\s*\{[^}]*font-family:\s*"Source Serif 4"/);
    expect(themeCss).toMatch(/@font-face\s*\{[^}]*font-display:\s*swap/);
  });

  it("points at a local file rather than a CDN", () => {
    expect(themeCss).toMatch(/url\("\/fonts\/source-serif-4-latin-\d+\.woff2"\)/);
    expect(themeCss).not.toMatch(/url\("https?:\/\//);
  });
});

describe("the display face is applied at exactly four sites", () => {
  it("uses var(--font-display) only for the wordmark, hero, lens title, and stat value", () => {
    const sites = Array.from(
      themeCss.matchAll(/([^{}]+)\{([^}]*font-family:\s*var\(--font-display\)[^}]*)\}/g),
      (match) => match[1].trim(),
    );
    expect(sites.sort()).toEqual(
      [".brand__wordmark", ".hero__line", ".lens__title", ".ui-stat__value"].sort(),
    );
  });
});
