import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { OdiMascot } from "./OdiMascot";

describe("OdiMascot", () => {
  it("renders the vector chrome mark, not a pixel grid", () => {
    const { container } = render(<OdiMascot size={32} />);
    const svg = container.querySelector("svg");
    expect(svg).not.toBeNull();
    expect(svg?.getAttribute("viewBox")).toBe("0 0 32 32");
    expect(svg?.getAttribute("width")).toBe("32");
    expect(svg?.getAttribute("height")).toBe("32");
    // Smoothing is what we want on a curved mark; crisp edges would snap the
    // shapes back onto the pixel grid the vector mark exists to escape.
    expect(svg?.getAttribute("shape-rendering")).toBeNull();
    expect(svg?.querySelectorAll("ellipse").length).toBeGreaterThan(0);
    expect(svg?.querySelectorAll("path").length).toBeGreaterThan(0);
    // A 32 x 32 pixel grid emits hundreds of rects; the vector mark uses a
    // handful for the tile, the glasses lenses, and the nose.
    expect(svg?.querySelectorAll("rect").length).toBeLessThan(10);
  });

  it("is hidden from assistive technology", () => {
    const { container } = render(<OdiMascot />);
    expect(container.querySelector("svg")?.getAttribute("aria-hidden")).toBe("true");
    expect(screen.queryByRole("img")).toBeNull();
  });

  it("defaults to 32 pixels so the 32-pixel grid stays crisp", () => {
    const { container } = render(<OdiMascot />);
    expect(container.querySelector("svg")?.getAttribute("width")).toBe("32");
  });
});
