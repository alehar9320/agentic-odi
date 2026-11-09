import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

// The stylesheet is read from source rather than via a `?raw` import so the
// test does not depend on a CSS loader plugin being present in the runner.
const themeCss = readFileSync(
  fileURLToPath(new URL("./theme.css", import.meta.url)),
  "utf8",
);

describe("display face", () => {
  it("declares a serif display family on a token", () => {
    expect(themeCss).toMatch(/--font-display:\s*"[^"]*"/);
    expect(themeCss).toMatch(/--font-display:[^;]*serif/);
  });

  it("self-hosts EB Garamond rather than pointing at a remote URL", () => {
    expect(themeCss).toMatch(/@font-face\s*\{[^}]*font-family:\s*"EB Garamond"/s);
    expect(themeCss).toMatch(/src:\s*url\("\/fonts\/eb-garamond-(regular|medium|bold)\.ttf"\)/);
    expect(themeCss).toMatch(/font-display:\s*swap/);
    // No remote font URL anywhere in the stylesheet.
    expect(themeCss).not.toMatch(/https?:\/\/[^)]*\.woff|https?:\/\/[^)]*\.ttf/);
  });

  it("the four sites that matter opt in to the display face", () => {
    // `[^}]*` stops at the first `}`, so a rule that uses `var(--token)` is
    // matched only up to the closing paren. Allow nested parens instead.
    const blockRegex = (selector: string) =>
      new RegExp(
        `${selector.replace(/\./g, "\\.")}\\s*\\{(?:[^{}]|\\([^{}]*\\))*\\}`,
        "g",
      );
    for (const selector of [".hero__line", ".ui-stat__value", ".brand__wordmark", ".lens__title"]) {
      const blocks = [...themeCss.matchAll(blockRegex(selector))];
      expect(blocks, `${selector} should exist`).not.toHaveLength(0);
      // Some selectors appear more than once (a hover variant and the base
      // rule); at least one of them must opt in to the display face.
      expect(
        blocks.some(([full]) => full.includes("font-family: var(--font-display)")),
      ).toBe(true);
    }
  });
});

describe("type scale", () => {
  const sizes = ["4xl", "3xl", "2xl", "xl", "lg", "base", "md", "sm", "xs", "2xs"];

  it("declares every step", () => {
    for (const size of sizes) {
      expect(themeCss).toMatch(new RegExp(`--text-${size}:\\s*[^;]+;`));
    }
  });

  it("is anchored in rem so it scales with the user", () => {
    expect(themeCss).toMatch(/--text-base:\s*1\.125rem/);
    expect(themeCss).toMatch(/--text-4xl:\s*clamp\(/);
  });
});

describe("spacing scale", () => {
  it("declares a full run from zero to eight", () => {
    for (let i = 0; i <= 8; i++) {
      expect(themeCss).toMatch(new RegExp(`--space-${i}:\\s*[^;]+;`));
    }
  });

  it("starts at zero", () => {
    expect(themeCss).toMatch(/--space-0:\s*0;/);
  });
});