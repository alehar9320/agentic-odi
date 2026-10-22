import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { OdiMascot } from "./OdiMascot";

describe("OdiMascot", () => {
  it("renders the pixel-art mark", () => {
    const { container } = render(<OdiMascot size={32} />);
    const svg = container.querySelector("svg");
    expect(svg).not.toBeNull();
    expect(svg?.getAttribute("viewBox")).toBe("0 0 32 32");
    expect(svg?.getAttribute("width")).toBe("32");
    expect(svg?.getAttribute("height")).toBe("32");
    expect(svg?.getAttribute("shape-rendering")).toBe("crispEdges");
    expect(svg?.querySelectorAll("rect").length).toBeGreaterThan(10);
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
