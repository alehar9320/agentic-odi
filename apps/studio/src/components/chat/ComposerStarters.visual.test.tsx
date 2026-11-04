import { configure } from "@chromatic-com/vitest";
import { afterAll, afterEach, beforeEach, expect, it, vi } from "vitest";
import { page } from "vitest/browser";
import { render } from "vitest-browser-react";

import "../../styles/theme.css";
import { StudioRuntimeProvider } from "../../assistant/StudioRuntime";
import type { StudioContextValue } from "../../state/StudioContext";
import { SuggestionPills } from "./composerParts";

vi.mock("../../state/StudioContext", () => ({
  useStudio: vi.fn(),
}));

import { useStudio } from "../../state/StudioContext";

// The build table would otherwise name this `ComposerStarters.visual` after the
// test file rather than the surface it covers.
configure({ title: "ComposerStarters" });

// The visual config pins one Chromium instance at 900×700; the phone width is
// what #601 is about, so the two snapshots render there and the shared viewport
// is put back afterwards. One viewport, two themes, two snapshots — no matrix.
const PHONE = { width: 390, height: 700 };
const SHARED = { width: 900, height: 700 };

const FIRST_STARTER = "Turn 40 interview notes into one bet";
const LANDSCAPE = "Opportunity landscape";

const stubContext = (overrides: Record<string, unknown> = {}) =>
  ({
    messages: [],
    canvas: null,
    llmHealth: { healthy: true, message: "" },
    streaming: false,
    openPanel: vi.fn(),
    sendMessage: vi.fn(async () => {}),
    regenerateFrom: vi.fn(),
    editFrom: vi.fn(),
    switchBranch: vi.fn(),
    respondToApproval: vi.fn(),
    stopStreaming: vi.fn(),
    ...overrides,
  }) as unknown as StudioContextValue;

const originalTheme = document.documentElement.className;

// Chromatic captures the snapshot in its own `afterEach`, which runs before a
// later-registered `afterEach` here, so restoring the viewport there would leave
// the phone snapshots at the shared width. A `beforeEach` sets the phone width
// for capture; the file-level `afterAll` puts the shared 900×700 back so the
// next visual file is unaffected.
beforeEach(async () => {
  await page.viewport(PHONE.width, PHONE.height);
});

afterEach(() => {
  document.documentElement.className = originalTheme;
  vi.mocked(useStudio).mockReset();
});

afterAll(async () => {
  await page.viewport(SHARED.width, SHARED.height);
});

/**
 * The real `SuggestionPills` over a stubbed studio context, so a regression in
 * `theme.css` — not a copied markup fragment — is what the snapshot catches.
 * The theme class goes on the document element, where the app puts it, because
 * the light-theme surface rule resolves from a themed root.
 */
async function renderStarters(theme: "dark" | "light") {
  vi.mocked(useStudio).mockReturnValue(stubContext());
  document.documentElement.className = `theme-${theme}`;
  return render(
    <div style={{ width: "100%", padding: 16 }}>
      <StudioRuntimeProvider>
        <SuggestionPills />
      </StudioRuntimeProvider>
    </div>,
  );
}

function starterRow(container: HTMLElement): HTMLElement {
  const row = container.querySelector<HTMLElement>(".composer__pills");
  expect(row, "expected the starter row to render").not.toBeNull();
  return row!;
}

/** A phone holds one starter per line, with nothing spilling sideways. */
function expectOneColumn(container: HTMLElement) {
  expect(getComputedStyle(starterRow(container)).flexDirection).toBe("column");
  expect(document.documentElement.scrollWidth).toBeLessThanOrEqual(window.innerWidth);
}

function channels(color: string): number[] {
  return Array.from(color.match(/\d+(?:\.\d+)?/g) ?? [], Number);
}

/**
 * The card's fill composited over the page behind it. A translucent tint is
 * only visible through what it does to the page colour, so comparing the raw
 * `rgba()` strings would pass for a tint that is not there.
 */
function compositedFill(card: HTMLElement, host: HTMLElement): number[] {
  const [r, g, b, a = 1] = channels(getComputedStyle(card).backgroundColor);
  const [pr, pg, pb] = channels(getComputedStyle(host).backgroundColor);
  return [r, g, b].map((channel, index) => channel * a + [pr, pg, pb][index] * (1 - a));
}

it("stacks the starter set into one column in the dark theme on a phone", async () => {
  const screen = await renderStarters("dark");

  await expect.element(screen.getByRole("button", { name: FIRST_STARTER })).toBeVisible();
  await expect.element(screen.getByRole("button", { name: LANDSCAPE })).toBeVisible();

  expectOneColumn(screen.container);
});

it("gives the starter set a visible surface in the light theme on a phone", async () => {
  const screen = await renderStarters("light");

  await expect.element(screen.getByRole("button", { name: FIRST_STARTER })).toBeVisible();

  expectOneColumn(screen.container);

  // The dark-only 2.5% white alpha leaves the card indistinguishable from the
  // page in light theme; the surface has to move the pixels a person can see.
  const card = screen.container.querySelector<HTMLElement>(".suggestion")!;
  const fill = compositedFill(card, document.body);
  const page = channels(getComputedStyle(document.body).backgroundColor);
  const delta = fill.map((channel, index) => Math.abs(channel - page[index]));
  expect(Math.max(...delta)).toBeGreaterThanOrEqual(6);
});
