import { describe, expect, it } from "vitest";

import mainSource from "../main.tsx?raw";
import vendorCss from "../vendor/index.css?raw";
import briefCss from "./brief.css?raw";
import entryCss from "./entry.css?raw";
import recordsCss from "./records.css?raw";
import themeCss from "./theme.css?raw";

/**
 * The cascade order has exactly one home: `entry.css`.
 *
 * An unlayered rule outranks every layered one, specificity included, so the
 * product stylesheet is only overridable by a copied component's utilities
 * while it sits in a layer that is declared before `utilities` (issue #384).
 * That makes the order itself the thing to guard: a second `@layer` statement,
 * or a stylesheet imported directly again, silently re-lowers the layer.
 *
 * The behaviour is proven in a real browser by `src/vendor/layering.visual.test.tsx`;
 * jsdom resolves no cascade for `@layer`, so nothing here claims to measure it.
 */

function layerOrder(source: string): string[] {
  const statement = source.match(/@layer\s+([^;{]+);/);
  expect(statement, "entry.css declares no @layer order").not.toBeNull();
  return statement![1].split(",").map((name) => name.trim());
}

describe("the product stylesheet layer", () => {
  it("ranks product rules below the vendor utilities", () => {
    const order = layerOrder(entryCss);
    expect(order.indexOf("product")).toBeLessThan(order.indexOf("utilities"));
  });

  it("ranks product rules above the tokens they must be able to set", () => {
    const order = layerOrder(entryCss);
    // Tailwind's `theme` layer only carries custom properties; the product sheet
    // defines the app's own tokens, so it must not sit beneath them.
    expect(order.indexOf("product")).toBeGreaterThan(order.indexOf("theme"));
  });

  it("imports every product sheet into that layer and the vendor sheet as generated", () => {
    expect(entryCss).toContain('@import "./theme.css" layer(product)');
    expect(entryCss).toContain('@import "./records.css" layer(product)');
    expect(entryCss).toContain('@import "./brief.css" layer(product)');
    expect(entryCss).toMatch(/@import\s+"[^"]*vendor\/index\.css"/);
  });

  it("is the only file that states the order", () => {
    for (const [name, source] of [
      ["main.tsx", mainSource],
      ["theme.css", themeCss],
      ["records.css", recordsCss],
      ["brief.css", briefCss],
    ] as const) {
      expect(source, `${name} declares its own @layer order`).not.toMatch(/@layer\s+[A-Za-z]/);
    }
    expect(vendorCss).not.toMatch(/@layer[^;]*product/);
  });

  it("is the only stylesheet the app entry imports", () => {
    const imported = Array.from(mainSource.matchAll(/import\s+"([^"]+\.css)"/g), (m) => m[1]);
    expect(imported).toEqual(["./styles/entry.css"]);
  });
});
