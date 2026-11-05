import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import themeCss from "../../styles/theme.css?raw";
import { StatusDot } from "./StatusDot";
import type { StatusTone } from "./StatusDot";

const TONES: StatusTone[] = ["ok", "warn", "unknown", "busy", "ready"];

/**
 * The bug this file exists for: a shared `::before` rule painted a second,
 * 6 px `currentColor` disc on top of every `.status-dot`, and planted a dot
 * inside `.studio-pill` labels that never asked for one. jsdom cannot evaluate
 * a stylesheet, so the shape of the fix is checked two ways — the component
 * renders one node with nothing inside it, and the stylesheet no longer
 * contains the injection.
 */
describe("StatusDot", () => {
  it("paints exactly one element per tone", () => {
    for (const tone of TONES) {
      const { container } = render(<StatusDot tone={tone} />);
      expect(container.querySelectorAll("*").length).toBe(1);
      expect(container.firstElementChild?.className).toContain("status-dot");
    }
  });

  it("carries the tone modifier the base class does not already paint", () => {
    const MODIFIER: Record<StatusTone, string> = {
      ok: "status-dot",
      warn: "status-dot is-warn",
      unknown: "status-dot is-unknown",
      busy: "status-dot is-busy",
      ready: "status-dot is-ready",
    };
    for (const tone of TONES) {
      const { container } = render(<StatusDot tone={tone} />);
      expect(container.firstElementChild?.className).toBe(MODIFIER[tone]);
    }
  });

  it("holds nothing inside itself", () => {
    for (const tone of TONES) {
      const { container } = render(<StatusDot tone={tone} />);
      expect(container.firstElementChild?.childNodes.length).toBe(0);
    }
  });

  it("is decorative until it is given a label", () => {
    const { container } = render(<StatusDot tone="ok" />);
    expect(container.firstElementChild?.getAttribute("aria-hidden")).toBe("true");
    expect(screen.queryByRole("img")).toBeNull();
  });

  it("becomes an image with a name when a label is worth reading", () => {
    render(<StatusDot tone="ok" label="Unread signal" />);
    const dot = screen.getByRole("img", { name: "Unread signal" });
    expect(dot.getAttribute("aria-hidden")).toBeNull();
    expect(dot.childNodes.length).toBe(0);
  });
});

describe("the stylesheet that used to inject a second dot", () => {
  it("paints one disc, not two", () => {
    expect(themeCss).not.toMatch(
      /status-dot::before|studio-pill::before|pill-(green|amber|blue)::before/,
    );
  });

  it("lays out a dot outside a flex row and a pill without a pseudo-element", () => {
    expect(themeCss).toMatch(/\.status-dot\s*\{[^}]*display:\s*inline-block/);
    expect(themeCss).toMatch(/\.studio-pill\s*\{[^}]*display:\s*inline-flex/);
  });

  it("keeps a ring when forced-colors suppresses the background", () => {
    expect(themeCss).toMatch(
      /@media\s*\(forced-colors:\s*active\s*\)\s*\{\s*\.status-dot\s*\{[^}]*border:[^}]*CanvasText/,
    );
  });
});
