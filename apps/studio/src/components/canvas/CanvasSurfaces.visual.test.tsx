import { configure } from "@chromatic-com/vitest";
import { expect, it, vi } from "vitest";
import { render } from "vitest-browser-react";

import "../../styles/theme.css";
import type { CanvasData, CanvasState } from "../../types";
import { JobMap } from "./JobMap";
import { OpportunityLandscape } from "./OpportunityLandscape";

// The build table would otherwise name these after the file rather than the
// two canvas surfaces they photograph.
configure({ title: "Canvas surfaces" });

const canvasData: CanvasData = {
  jobs: [{ id: "JOB-1", name: "Onboard a new account" }],
  steps: [
    { id: "STEP-1", job_id: "JOB-1", name: "Import the interview recordings", order: 1 },
    { id: "STEP-2", job_id: "JOB-1", name: "Quote the blockers", order: 2 },
  ],
  outcomes: [
    {
      id: "O-101",
      job_id: "JOB-1",
      statement: "Minimize the time to get help",
      importance: 9,
      satisfaction: 2,
      opportunity_score: 16,
    },
    {
      id: "O-102",
      job_id: "JOB-1",
      statement: "Keep the setup notes with the account",
      importance: 8,
      satisfaction: 7,
      opportunity_score: 9,
    },
  ],
  evidence: [],
  source: "local",
};

const harness = vi.hoisted(() => ({
  state: {
    canvasState: { kind: "loading", data: null } as CanvasState,
    refreshCanvas: vi.fn(),
    openPanel: vi.fn(),
    sendMessage: vi.fn(),
    pushToast: vi.fn(),
    deleteThesis: vi.fn(),
    saveThesis: vi.fn(),
    ask: vi.fn(),
    deleteOutcome: vi.fn(),
    updateOutcome: vi.fn(),
    addStep: vi.fn(),
    updateStep: vi.fn(),
    deleteStep: vi.fn(),
    updateJob: vi.fn(),
    deleteJob: vi.fn(),
    theses: [],
    focusedJobId: null as string | null,
    focusedSubject: null as { kind: string; id: string } | null,
    focusSubject: vi.fn(),
  },
}));

vi.mock("../../state/StudioContext", () => ({
  useStudio: () => harness.state,
}));

/**
 * The theme class goes on the document element, where the app puts it, because
 * the canvas tokens are aliases of theme tokens and resolve from a themed root.
 */
function themed(theme: "dark" | "light") {
  document.documentElement.className = `theme-${theme}`;
}

function painted(container: HTMLElement, selector: string): CSSStyleDeclaration {
  const element = container.querySelector<HTMLElement>(selector);
  expect(element, `expected ${selector} to render`).not.toBeNull();
  return getComputedStyle(element!);
}

/**
 * A `var()` naming a property nobody defines invalidates the declaration at
 * computed-value time, and the property falls back to its initial value: no
 * background, `border-style: none`, inherited text. So each check below is the
 * difference between the canvas being themed and the canvas merely being
 * styled — and it is the class of bug that shipped silently in the first place.
 */
function expectAliasResolution() {
  const root = getComputedStyle(document.documentElement);
  const token = (name: string) => root.getPropertyValue(name).trim();

  // Each alias must resolve to the canonical token of the theme in force.
  expect(token("--studio-muted")).toBe(token("--muted"));
  expect(token("--studio-surface")).toBe(token("--surface"));
  expect(token("--studio-border")).toBe(token("--line"));
}

function expectLandscapePaint(container: HTMLElement) {
  // The selected view button is a gradient fill; `none` means the aliases broke.
  const primary = painted(container, ".studio-button--primary");
  expect(primary.backgroundImage).toContain("linear-gradient(");

  // The metric cards are cards: a 1px solid border, not the shorthand's initial
  // `none` that a dropped `var(--studio-border)` leaves behind.
  const metric = painted(container, ".studio-metric");
  expect(metric.borderTopStyle).toBe("solid");
  expect(metric.borderTopWidth).toBe("1px");
}

it("paints the landscape in the dark theme", async () => {
  harness.state.canvasState = { kind: "ready", data: canvasData };
  themed("dark");
  const screen = await render(<OpportunityLandscape />);

  await expect.element(screen.getByRole("button", { name: /Visual Cards/ })).toBeVisible();
  expectAliasResolution();
  expectLandscapePaint(screen.container);
});

it("paints the landscape in the light theme", async () => {
  harness.state.canvasState = { kind: "ready", data: canvasData };
  themed("light");
  const screen = await render(<OpportunityLandscape />);

  await expect.element(screen.getByRole("button", { name: /Visual Cards/ })).toBeVisible();
  expectAliasResolution();
  expectLandscapePaint(screen.container);
});

it("gives the landscape's empty state a surface", async () => {
  harness.state.canvasState = { kind: "empty", data: canvasData };
  themed("light");
  const screen = await render(<OpportunityLandscape />);

  await expect.element(screen.getByText("No opportunities yet")).toBeVisible();

  const empty = painted(screen.container, ".studio-empty");
  expect(empty.backgroundColor).not.toBe("rgba(0, 0, 0, 0)");
  expect(empty.borderTopStyle).toBe("solid");
  expect(empty.borderRadius).toBe("10px");
});

it("paints the job map in the dark theme", async () => {
  harness.state.canvasState = { kind: "ready", data: canvasData };
  themed("dark");
  const screen = await render(<JobMap />);

  await expect.element(screen.getByRole("list", { name: "Job steps" })).toBeVisible();

  // The step rows carry their surface and border as inline styles, which fail
  // the same way a stylesheet rule does when the token is missing.
  const row = painted(screen.container, ".step-row");
  expect(row.borderTopStyle).toBe("solid");
  expect(row.backgroundColor).not.toBe("rgba(0, 0, 0, 0)");
  expectAliasResolution();
});

it("paints the job map in the light theme", async () => {
  harness.state.canvasState = { kind: "ready", data: canvasData };
  themed("light");
  const screen = await render(<JobMap />);

  await expect.element(screen.getByRole("list", { name: "Job steps" })).toBeVisible();
  expect(painted(screen.container, ".step-row").borderTopStyle).toBe("solid");
  expectAliasResolution();
});
