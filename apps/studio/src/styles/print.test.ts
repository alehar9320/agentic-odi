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

  // The records lens is the surface a person takes to a meeting: its headings and tables
  // print, its controls and its row-cap notice do not, and a long table repeats its header
  // on every sheet rather than leaving page two unlabeled.
  it("prints the records lens as tables and hides what a reader cannot press on paper", () => {
    for (const selector of [".records__heading", ".records__table"]) {
      expect(printCss).toContain(selector);
    }
    expect(printCss).toMatch(/\.records__export,\s*\.records__cap\s*\{\s*display:\s*none/);
    expect(printCss).toMatch(/thead\s*\{[^}]*display:\s*table-header-group/);
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

  it("keeps the document's own text out of the hiding list", () => {
    const hiding = [...printCss.matchAll(/([^{}]+)\{([^}]*)\}/g)]
      .filter(([, , body]) => /display:\s*none/.test(body))
      .map(([, selectors]) => selectors.replace(/\s+/g, " ").trim())
      .filter((selectors) => selectors.includes("brief-printing"));

    expect(hiding.length).toBeGreaterThan(0);
    for (const selectors of hiding) {
      // Hiding the chrome is the point; hiding a paragraph, a heading, a list
      // or the document itself would print a paper with holes in it.
      expect(selectors).not.toMatch(/brief__doc|\.md-/);
    }
  });

  it("prints the brief dark on white and never orphans a heading or a line", () => {
    const rules = briefRules(printCss);
    expect(rules).toMatch(/\.brief__doc[^}]*color:\s*#111/s);
    expect(rules).toMatch(/\.brief__doc[^}]*break-inside:\s*avoid/s);
  });
});
