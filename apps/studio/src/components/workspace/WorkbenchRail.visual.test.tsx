import { configure } from "@chromatic-com/vitest";
import { userEvent } from "vitest/browser";
import { render } from "vitest-browser-react";
import { afterEach, expect, it, vi } from "vitest";

import "../../styles/theme.css";

// Chromatic would otherwise name this build `WorkbenchRail.visual` after the
// file; the surface is the map, and these are its four shapes.
configure({ title: "Studio map" });

const stub = vi.hoisted(() => {
  const noop = () => {};
  return {
    canvas: {
      jobs: [{ id: "J-1", name: "Deploy a service safely" }],
      steps: [
        { id: "S-1", job_id: "J-1", name: "Plan the release", order: 1 },
        { id: "S-2", job_id: "J-1", name: "Ship it", order: 2 },
      ],
      outcomes: [
        { id: "O-1", statement: "Cut deploy time on hotfixes", importance: 9, satisfaction: 3, opportunity_score: 6, evidence: "a quote" },
        { id: "O-2", statement: "See who rolled back", importance: 7, satisfaction: 4, opportunity_score: 3 },
        { id: "O-3", statement: "Trace a failure to a change", importance: 8, satisfaction: 2, opportunity_score: 6 },
      ],
      evidence: [
        { id: "E-1", name: "Support ticket", content: "We found it in the logs an hour later.", item_type: "quote" },
        { id: "E-2", name: "Interview", content: "I keep a spreadsheet of rollbacks.", item_type: "quote" },
      ],
      scheduled_work: [
        { id: "W-1", name: "Weekly scan", agent_id: "a", trigger_type: "cron", schedule_expression: "0 9 * * 1", status: "scheduled", created_at: "2026-10-01T00:00:00+00:00" },
      ],
      source: "mcp",
    } as Record<string, unknown>,
    studio: {
      canvas: {} as Record<string, unknown>,
      memory: [
        { id: "M-1", kind: "preference", text: "Owns activation.", data: {}, status: "confirmed", confidence: 0.9, source_turn: 3, created_at: "2026-10-01T00:00:00+00:00", updated_at: "2026-10-01T00:00:00+00:00" },
        { id: "M-2", kind: "preference", text: "Prefers short updates.", data: {}, status: "suggested", confidence: 0.5, source_turn: null, created_at: "2026-10-01T00:00:00+00:00", updated_at: "2026-10-01T00:00:00+00:00" },
      ] as Record<string, unknown>[],
      segments: [
        { id: "SEG-1", name: "Release owners", people: "4 teams", job_statement: "Deploy a service safely", outcome_ids: ["O-1"], rationale: "Two quotes.", confidence: 0.8, created_at: "2026-10-01T00:00:00+00:00" },
      ] as Record<string, unknown>[],
      signals: [] as unknown[],
      unreadSignalCount: 2,
      activePanel: "landscape",
      openPanel: noop,
      closePanel: noop,
    } as Record<string, unknown>,
  };
});

vi.mock("../../state/StudioContext", () => ({ useStudio: () => stub.studio }));

const originalMatchMedia = window.matchMedia;

/**
 * Review renders at 900px, where the map is a drawer, so the widths these shots
 * are about are pinned here rather than inherited from the harness. The CSS the
 * shot proves is still the production stylesheet.
 */
function atWidth(width: number): void {
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    writable: true,
    value: (query: string) => {
      const limit = Number(/max-width:\s*(\d+)px/.exec(query)?.[1] ?? Number.NaN);
      return {
        matches: Number.isFinite(limit) && width <= limit,
        media: query,
        onchange: null,
        addEventListener: () => {},
        removeEventListener: () => {},
      };
    },
  });
}

function inTheme(theme: "light" | "dark"): void {
  document.documentElement.classList.toggle("theme-light", theme === "light");
}

async function mount() {
  const { WorkbenchRail } = await import("./WorkbenchRail");
  return render(<WorkbenchRail />);
}

afterEach(() => {
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    writable: true,
    value: originalMatchMedia,
  });
  document.documentElement.classList.remove("theme-light");
  window.localStorage.clear();
});

it("maps every destination in the dark, wide", async () => {
  atWidth(1440);
  inTheme("dark");
  stub.studio.canvas = stub.canvas;

  const screen = await mount();

  await expect.element(screen.getByRole("button", { name: "Evidence, 2 quotes" })).toBeVisible();
  await expect.element(screen.getByRole("button", { name: "Landscape, 3 opportunities" })).toHaveAttribute(
    "aria-current",
    "page",
  );
});

it("maps every destination in the light, wide", async () => {
  atWidth(1440);
  inTheme("light");
  stub.studio.canvas = stub.canvas;

  const screen = await mount();

  await expect.element(screen.getByRole("button", { name: "What I know, 2 notes" })).toBeVisible();
});

it("holds the icons when it is collapsed, dark", async () => {
  atWidth(1440);
  inTheme("dark");
  window.localStorage.setItem("studio.sidebar", "collapsed");
  stub.studio.canvas = stub.canvas;

  const screen = await mount();

  const row = screen.getByRole("button", { name: "Landscape, 3 opportunities" });
  await expect.element(row).toBeVisible();
  await expect.element(row.getByText("Landscape")).not.toBeVisible();
});

it("holds the icons when it is collapsed, light", async () => {
  atWidth(1440);
  inTheme("light");
  window.localStorage.setItem("studio.sidebar", "collapsed");
  stub.studio.canvas = stub.canvas;

  await mount();
});

it("opens from an edge when the window is a phone", async () => {
  atWidth(800);
  inTheme("dark");
  stub.studio.canvas = stub.canvas;

  const screen = await mount();

  await userEvent.click(screen.getByRole("button", { name: "Studio map" }));
  await expect.element(screen.getByRole("dialog", { name: "Studio" })).toBeVisible();
});
