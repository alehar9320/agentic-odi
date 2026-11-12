import { configure } from "@chromatic-com/vitest";
import { afterEach, expect, it } from "vitest";
import { render } from "vitest-browser-react";

import "../../styles/theme.css";
import { PlugIcon } from "../icons";
import { StatusDot } from "./StatusDot";
import type { StatusTone } from "./StatusDot";

// Chromatic would otherwise name this build `StatusDot.visual` after the file.
configure({ title: "StatusDot" });

const TONES: StatusTone[] = ["ok", "warn", "unknown", "busy", "ready"];
const TONE_LABEL: Record<StatusTone, string> = {
  ok: "reachable",
  warn: "offline",
  unknown: "not checked",
  busy: "downloading",
  ready: "ready to install",
};

/**
 * The two surfaces the bug touched, rendered with their production classes and
 * no test-only styling: a Settings-style column of dots, and the bar's two
 * label pills. A fixture that invented its own CSS would pass whether the
 * stylesheet was right or not.
 */
function Fixture() {
  return (
    <div style={{ width: 420, padding: 24, background: "var(--bg)" }}>
      <ul className="connection-list" style={{ listStyle: "none", margin: 0, padding: 0 }}>
        {TONES.map((tone) => (
          <li key={tone}>
            <StatusDot tone={tone} />
            <span>{TONE_LABEL[tone]}</span>
          </li>
        ))}
      </ul>
      <div className="bar__right" style={{ marginTop: 24 }}>
        <button type="button" className="studio-pill pill-customize" aria-label="Customize connectors">
          <PlugIcon size={15} />
          Customize
        </button>
        <button type="button" className="studio-pill pill-changelog" aria-label="Open What's New changelog">
          ✨ What’s New
        </button>
      </div>
    </div>
  );
}

function useTheme(theme: "theme-dark" | "theme-light") {
  document.documentElement.className = theme;
  afterEach(() => {
    document.documentElement.className = "";
  });
}

const sizeOf = (el: Element) => {
  const box = el.getBoundingClientRect();
  return `${Math.round(box.width)}x${Math.round(box.height)}`;
};

/** The injected second disc, if any, is what this reads. */
const pseudoContent = (el: Element) =>
  getComputedStyle(el, "::before").content.replace(/"/g, "");

async function renderFixture() {
  const { container } = await render(<Fixture />);
  return container;
}

it("shows one solid disc per tone and no dot inside the pills — dark", async () => {
  useTheme("theme-dark");
  const container = await renderFixture();

  const dots = container.querySelectorAll(".status-dot");
  expect(dots.length).toBe(TONES.length);
  for (const dot of dots) {
    expect(sizeOf(dot)).toBe("7x7");
    // One disc: the dot itself carries no pseudo-element of any kind.
    expect(pseudoContent(dot)).toBe("none");
  }

  // Five distinct states must not collapse into one color: ok and ready share
  // green, the other three each paint differently.
  const painted = [...dots].map((dot) => getComputedStyle(dot).backgroundColor);
  expect(new Set(painted).size).toBe(4);

  const pills = container.querySelectorAll(".studio-pill");
  expect(pills.length).toBe(2);
  for (const pill of pills) {
    expect(pseudoContent(pill)).toBe("none");
  }
});

it("shows the same discs on the light surface — light", async () => {
  useTheme("theme-light");
  const container = await renderFixture();

  const dots = container.querySelectorAll(".status-dot");
  for (const dot of dots) {
    expect(sizeOf(dot)).toBe("7x7");
    expect(pseudoContent(dot)).toBe("none");
  }
  const ok = dots[0] as HTMLElement;
  expect(getComputedStyle(ok).backgroundColor).not.toBe("rgba(0, 0, 0, 0)");

  for (const pill of container.querySelectorAll(".studio-pill")) {
    expect(pseudoContent(pill)).toBe("none");
  }
});
