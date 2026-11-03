import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { contrastWalker, formatFindings } from "./contrast";

/**
 * The walker's own tests (issue #543, parent #331).
 *
 * `e2e/a11y.spec.ts` runs this same source against the real Studio in a
 * browser. These tests run it against jsdom fixtures instead, so the math and
 * the failure shape are covered without a browser: the known contrast anchors,
 * the ancestor and gradient resolution, the thresholds by text size, and the
 * `indeterminate` verdict for a background that cannot be read.
 *
 * jsdom has no layout, so every fixture is given a non-zero box. That is the
 * one thing the browser supplies for free.
 */

const SIZE = {
  width: 120,
  height: 24,
  top: 0,
  left: 0,
  right: 120,
  bottom: 24,
  x: 0,
  y: 0,
  toJSON() {},
};

beforeEach(() => {
  Object.defineProperty(Element.prototype, "getBoundingClientRect", {
    configurable: true,
    value: () => SIZE,
  });
});

afterEach(() => {
  document.body.innerHTML = "";
});

/** A paragraph with direct text, wired the way the app wires one. */
function paragraph(styles: Partial<CSSStyleDeclaration>): HTMLParagraphElement {
  const element = document.createElement("p");
  element.textContent = "Sample caption";
  Object.assign(element.style, styles);
  document.body.appendChild(element);
  return element;
}

describe("contrastWalker", () => {
  it("measures the known anchors: black on white is 21:1", () => {
    // Both extremes clear 4.5:1, so a correct walker reports nothing.
    paragraph({ color: "rgb(0, 0, 0)", background: "rgb(255, 255, 255)" });
    expect(contrastWalker(document.body, "fixture", "dark")).toEqual([]);
    document.body.innerHTML = "";
    paragraph({ color: "rgb(255, 255, 255)", background: "rgb(0, 0, 0)" });
    expect(contrastWalker(document.body, "fixture", "dark")).toEqual([]);

    // White on white is the other known anchor: 1:1.
    document.body.innerHTML = "";
    paragraph({ color: "rgb(255, 255, 255)", background: "rgb(255, 255, 255)" });
    const [finding] = contrastWalker(document.body, "fixture", "dark");
    expect(finding.ratio).toBeCloseTo(1, 5);
    expect(finding.required).toBe(4.5);
  });

  it("names the selector, both colours, and the ratio for a failure", () => {
    paragraph({ color: "rgb(154, 160, 170)", background: "rgb(162, 167, 179)" });
    const findings = contrastWalker(document.body, "home", "dark");
    expect(findings).toHaveLength(1);
    expect(findings[0]).toMatchObject({
      screen: "home",
      theme: "dark",
      foreground: "rgb(154, 160, 170)",
      background: "rgb(162, 167, 179)",
      required: 4.5,
      reason: "ratio",
    });
    expect(findings[0].ratio).toBeLessThan(1.5);
    expect(formatFindings(findings)).toContain("screen=home");
  });

  it("holds large text to 3:1 and body text to 4.5:1", () => {
    // White on rgb(99, 102, 241) is 4.47:1 — under the body threshold but over
    // the large-text one.
    const large = paragraph({
      color: "rgb(255, 255, 255)",
      background: "rgb(99, 102, 241)",
      fontSize: "24px",
    });
    expect(contrastWalker(document.body, "fixture", "dark")).toEqual([]);
    large.style.fontSize = "16px";
    expect(contrastWalker(document.body, "fixture", "dark")).toHaveLength(1);
  });

  it("composites a translucent surface over the opaque layer behind it", () => {
    const shell = document.createElement("div");
    shell.style.background = "rgb(10, 11, 14)";
    const element = document.createElement("p");
    element.textContent = "Sample caption";
    element.style.color = "rgb(255, 255, 255)";
    element.style.background = "rgba(255, 255, 255, 0.5)";
    shell.appendChild(element);
    document.body.appendChild(shell);

    // White text over white-over-black (mid grey) is unreadable.
    const findings = contrastWalker(document.body, "fixture", "dark");
    expect(findings).toHaveLength(1);
    expect(findings[0].background).toBe("rgb(133, 133, 135)");
  });

  it("judges text against the worst stop of a gradient", () => {
    const element = paragraph({
      color: "rgb(255, 255, 255)",
      backgroundImage: "linear-gradient(90deg, rgb(0, 0, 0), rgb(255, 255, 255))",
    });
    const findings = contrastWalker(element, "fixture", "dark");
    expect(findings).toHaveLength(1);
    // The white stop, not the black one, is the failure.
    expect(findings[0].background).toBe("rgb(255, 255, 255)");
    expect(findings[0].ratio).toBeCloseTo(1, 5);
  });

  it("reports an unreadable image as indeterminate instead of skipping it", () => {
    const element = paragraph({
      color: "rgb(0, 0, 0)",
      backgroundImage: "url(photo.png)",
    });
    const findings = contrastWalker(element, "fixture", "dark");
    expect(findings).toHaveLength(1);
    expect(findings[0]).toMatchObject({ reason: "indeterminate", background: null, ratio: null });
  });

  it("ignores hidden and zero-size text", () => {
    paragraph({ color: "rgb(0, 0, 0)", background: "rgb(0, 0, 0)", visibility: "hidden" });
    paragraph({ color: "rgb(0, 0, 0)", background: "rgb(0, 0, 0)", display: "none" });
    paragraph({ color: "rgb(0, 0, 0)", background: "rgb(0, 0, 0)", opacity: "0" });
    expect(contrastWalker(document.body, "fixture", "dark")).toEqual([]);
  });

  it("ignores an element whose text is in a child, not in it", () => {
    const parent = document.createElement("div");
    const child = document.createElement("p");
    child.textContent = "Sample caption";
    child.style.color = "rgb(0, 0, 0)";
    child.style.background = "rgb(0, 0, 0)";
    parent.appendChild(child);
    document.body.appendChild(parent);

    const findings = contrastWalker(document.body, "fixture", "dark");
    // Only the child owns the text, so only the child is judged.
    expect(findings).toHaveLength(1);
    expect(findings[0].selector).toContain("p");
  });
});

describe("formatFindings", () => {
  it("orders the worst ratio first and never hides an indeterminate pair", () => {
    const text = formatFindings([
      {
        screen: "home",
        theme: "dark",
        selector: "p.a",
        text: "a",
        foreground: "rgb(1, 1, 1)",
        background: "rgb(2, 2, 2)",
        ratio: 2.5,
        required: 4.5,
        reason: "ratio",
      },
      {
        screen: "home",
        theme: "dark",
        selector: "p.b",
        text: "b",
        foreground: "rgb(3, 3, 3)",
        background: null,
        ratio: null,
        required: 4.5,
        reason: "indeterminate",
      },
      {
        screen: "home",
        theme: "dark",
        selector: "p.c",
        text: "c",
        foreground: "rgb(4, 4, 4)",
        background: "rgb(5, 5, 5)",
        ratio: 1.1,
        required: 4.5,
        reason: "ratio",
      },
    ]);
    const lines = text.split("\n");
    // An unmeasurable pair sorts first: it cannot be judged until a human
    // resolves it. Then the worst measured ratio.
    expect(lines[0]).toContain("ratio=indeterminate");
    expect(lines[1]).toContain("selector=p.c");
    expect(lines[2]).toContain("selector=p.a");
  });
});
