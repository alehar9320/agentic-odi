import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { OdiMascot } from "./OdiMascot";

describe("OdiMascot", () => {
  it("renders the vector mark, not a per-pixel rect grid", () => {
    const { container } = render(<OdiMascot size={32} />);
    const svg = container.querySelector("svg");
    expect(svg).not.toBeNull();
    expect(svg?.getAttribute("viewBox")).toBe("0 0 32 32");
    expect(svg?.getAttribute("width")).toBe("32");
    expect(svg?.getAttribute("height")).toBe("32");
    // Smoothing is what we want on a curved mark, so the browser is free to
    // antialias it at any device-pixel ratio.
    expect(svg?.getAttribute("shape-rendering")).toBeNull();
    // Curves carry the face; a 32 × 32 grid would be hundreds of rects.
    expect(svg?.querySelectorAll("ellipse").length).toBeGreaterThan(0);
    expect(svg?.querySelectorAll("path").length).toBeGreaterThan(0);
    expect(svg?.querySelectorAll("rect").length).toBeLessThan(10);
  });

  it("is hidden from assistive technology", () => {
    const { container } = render(<OdiMascot />);
    expect(container.querySelector("svg")?.getAttribute("aria-hidden")).toBe("true");
    expect(screen.queryByRole("img")).toBeNull();
  });

  it("defaults to 32 pixels so the mark fills its slot", () => {
    const { container } = render(<OdiMascot />);
    expect(container.querySelector("svg")?.getAttribute("width")).toBe("32");
  });
});
