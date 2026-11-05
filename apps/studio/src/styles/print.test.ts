import { describe, expect, it } from "vitest";

import printCss from "./print.css?raw";
import themeCss from "./theme.css?raw";

describe("print stylesheet", () => {
  it("targets print media", () => {
    expect(printCss).toMatch(/@media print\s*\{/);
  });

  it("hides the studio chrome so only the work prints", () => {
    for (const selector of [".bar", ".composer", ".rail", ".scrim"]) {
      expect(printCss).toContain(selector);
    }
    expect(printCss).toMatch(/display:\s*none/);
  });

  it("lays the page out for A4 and keeps a card on one sheet", () => {
    expect(printCss).toContain("size: A4");
    expect(printCss).toContain("break-inside: avoid");
  });

  it("is loaded by the studio theme", () => {
    expect(themeCss).toContain('@import "./print.css"');
  });
});

/**
 * The brief sheet marks the body while the print dialog is open, so the page
 * can be the document rather than whatever happened to be on screen.
 */
function briefRules(css: string): string {
  return (css.match(/body\.brief-printing[^{]*\{[^}]*\}/g) ?? []).join("\n");
}

describe("decision brief print", () => {
  it("keeps the conversation and the studio chrome off the page", () => {
    const rules = briefRules(printCss);
    expect(rules).not.toBe("");
    for (const selector of [".chat", ".bar", ".composer", ".lens__head", ".lens__foot"]) {
      expect(rules).toContain(selector);
    }
    expect(rules).toMatch(/display:\s*none/);
  });

  it("hides the sheet's own controls, which are not part of the document", () => {
    const rules = briefRules(printCss);
    expect(rules).toContain(".brief__bar");
    expect(rules).toContain(".brief__objection");
  });

  it("prints the brief dark on white and never orphans a heading or a line", () => {
    const rules = briefRules(printCss);
    expect(rules).toMatch(/\.brief__doc[^}]*color:\s*#111/s);
    expect(rules).toMatch(/\.brief__doc[^}]*break-inside:\s*avoid/s);
  });
});

/**
 * The surfaces Tasks 3 and 4 converted to the palette. A token follows the
 * theme, and the theme is a screen: on paper `--plot-surface` is still the dark
 * ground and `--muted` is still light ink, so the sheet that prints has to say
 * what ink on paper is, class by class.
 */
const CONVERTED = [
  ".opportunity-matrix__panel",
  ".opportunity-matrix__axes",
  ".opportunity-matrix__grid",
  ".opportunity-matrix__axis",
  ".opportunity-matrix__band",
  ".opportunity-matrix__zone-label--underserved",
  ".opportunity-matrix__zone-label--overserved",
  ".opportunity-matrix__node",
  ".opportunity-matrix__node--served",
  ".opportunity-matrix__node--underserved",
  ".opportunity-matrix__node--deep",
  ".opportunity-matrix__node-edge--underserved",
  ".opportunity-matrix__node-edge--deep",
  ".opportunity-matrix__label",
  ".opportunity-matrix__legend",
  ".opportunity-matrix__key--served",
  ".opportunity-matrix__key--underserved",
  ".opportunity-matrix__key--deep",
  ".opportunity-matrix__header-row",
  ".opportunity-matrix__row--underserved",
  ".opportunity-matrix__row--selected",
  ".opportunity-matrix__pill",
  ".opportunity-matrix__pill--underserved",
  ".jobmap__tile",
  ".jobmap__tile--selected",
  ".jobmap__tile--empty",
  ".jobmap__phase",
  ".jobmap__phase--empty",
  ".jobmap__desc",
  ".jobmap__pill--filled",
  ".jobmap__pill--empty",
];

/** Every rule in the sheet, as `selectors { declarations }`. */
function cssRules(css: string): string[] {
  return (css.match(/[^{}]+\{[^}]*\}/g) ?? []).map((rule) => rule.trim());
}

const canvasRules = cssRules(printCss).filter((rule) => /opportunity-matrix|jobmap/.test(rule));

describe("converted canvas surfaces on paper", () => {
  it("reaches every converted surface with a value of its own", () => {
    const unprinted = CONVERTED.filter(
      (selector) => !canvasRules.some((rule) => rule.includes(`${selector},`) || rule.includes(`${selector} {`)),
    );
    expect(unprinted).toEqual([]);
  });

  it("does not leave a canvas rule on a screen token", () => {
    // A `var(--…)` here is a dark screen value reaching paper.
    expect(canvasRules.filter((rule) => rule.includes("var(--"))).toEqual([]);
  });

  it("outranks the screen sheet instead of losing to it", () => {
    // theme.css imports print.css on its first line, so every screen rule comes
    // later and wins an equal-specificity fight. This file's `display: none`
    // rules already knew that; colour has to say it too.
    expect(themeCss.startsWith('@import "./print.css";')).toBe(true);
    const quiet = canvasRules.filter(
      (rule) => /(?:color|fill|stroke|background|box-shadow):/.test(rule) && !rule.includes("!important"),
    );
    expect(quiet).toEqual([]);
  });

  it("keeps the three bands separable as three greys", () => {
    const fillOf = (band: string): string | undefined =>
      new RegExp(`\\.opportunity-matrix__node--${band}\\s*\\{[^}]*fill:\\s*(#[0-9a-fA-F]{3,6})`).exec(
        printCss,
      )?.[1];
    const greys = ["served", "underserved", "deep"].map(fillOf);
    expect(greys).toEqual(["#444", "#888", "#111"]);
    // A legend swatch that disagrees with the marker it explains is a lie.
    for (const [index, band] of ["served", "underserved", "deep"].entries()) {
      expect(printCss).toMatch(
        new RegExp(`\\.opportunity-matrix__key--${band}\\s*\\{[^}]*background:\\s*${greys[index]}`),
      );
    }
  });
});
