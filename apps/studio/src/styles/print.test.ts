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
