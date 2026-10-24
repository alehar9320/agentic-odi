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
