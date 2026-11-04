import { expect, type Page, test } from "@playwright/test";
import { AxeBuilder } from "@axe-core/playwright";

import { COMPOSER, openStudio, rail, resetRepository, seedOutcomes } from "./helpers";
import {
  contrastWalker,
  formatFindings,
  staleKnownPairs,
  unlistedFindings,
  type ContrastFinding,
} from "../src/test/contrast";
import { KNOWN_PAIRS } from "./a11y/knownPairs";

/**
 * Contrast as a build gate (issue #543, parent #331).
 *
 * The jsdom sweep in `src/test/a11y.test.tsx` disables `color-contrast`
 * because jsdom has no layout, and `src/styles/theme.test.ts` measures the
 * palette tokens but never what a screen paints. This suite is the browser pass
 * those two deliberately leave open: it renders the core screens in both themes
 * and fails when a screen contains a pair that is not on the known list,
 * naming the screen, the selector, the two colours, and the ratio.
 *
 * Two checks run per screen and both must pass:
 *
 *   1. axe, scoped to `color-contrast`. Its violations are the pairs axe could
 *      resolve and found wanting.
 *   2. `contrastWalker` from `src/test/contrast.ts`, which resolves the
 *      gradient stops axe gives up on (axe returns those as `incomplete`) and
 *      reports a ratio for each, including a failure when it still cannot
 *      resolve the background. The same source runs in jsdom under
 *      `src/test/contrast.test.ts`.
 *
 * Only the contrast rule is gated. The other axe rules (`list`,
 * `target-size`, `scrollable-region-focusable`) already report violations on
 * this repository's own markup — the banner dock's Radix toast `<ol>` (#625)
 * among them — and this issue is the contrast slice, not the one that fixes
 * them. Running `color-contrast` alone keeps the gate honest: it fails on the
 * thing this issue is about and does not smuggle in a structural exemption
 * with no owner.
 *
 * Screens: home, the opportunity landscape, the records lens, the decision
 * brief, catch-up, and settings — each in both themes.
 */

const THEMES = ["dark", "light"] as const;
type Theme = (typeof THEMES)[number];

/**
 * Every screen fades in, and both checkers read the painted page: measured mid
 * animation a partially transparent element fails `color-contrast` for reasons
 * no user ever sees. The suite runs with reduced motion, which the stylesheet
 * honors by collapsing animations to their end state (`theme.css`), so the gate
 * measures the resting page deterministically.
 */
test.use({ reducedMotion: "reduce" });

/** The six core screens, each reachable through the shipped UI. */
const SCREENS = ["home", "landscape", "records", "brief", "catchup", "settings"] as const;
type Screen = (typeof SCREENS)[number];

const OUTCOME = {
  statement: "Minimize the time to deploy a service when releasing a hotfix",
  importance: 9.2,
  satisfaction: 3.1,
};

declare global {
  interface Window {
    __odiContrastScan: (root: Element, screen: string, theme: string) => ContrastFinding[];
  }
}

/** Force a theme before the app boots, the way the Settings panel would. */
async function setTheme(page: Page, theme: Theme): Promise<void> {
  await page.addInitScript((value) => {
    const raw = window.localStorage.getItem("studio.settings");
    const settings = raw ? JSON.parse(raw) : {};
    settings.theme = value;
    window.localStorage.setItem("studio.settings", JSON.stringify(settings));
  }, theme);
}

/**
 * Install the walker in the page. It is self-contained, so this is the whole
 * module: no bundling, no build step, no second copy to drift. Playwright
 * injects the source directly, so there is no `eval` in the page.
 */
async function installWalker(page: Page): Promise<void> {
  await page.addInitScript({
    content: `window.__odiContrastScan = ${contrastWalker.toString()};`,
  });
}

async function goto(page: Page, screen: Screen): Promise<void> {
  await openStudio(page);
  if (screen === "landscape" || screen === "records") {
    const label = screen === "landscape" ? "Landscape" : "Records";
    await rail(page).getByRole("button", { name: new RegExp(`^${label},`) }).click();
  } else if (screen === "brief") {
    // The command is the keyboard route, and the only one that reaches the
    // brief without a model.
    await page.getByRole("textbox", { name: COMPOSER }).fill("/brief");
    await page.keyboard.press("Enter");
  } else if (screen === "catchup") {
    await page.locator(".bar__bell").click();
  } else if (screen === "settings") {
    await page.getByRole("button", { name: "Open settings" }).click();
  }
  await expect(page.getByRole("main")).toBeVisible();
}

/**
 * Every pair the walker found across the screens this run. The known-pairs
 * list is global — one token pair shows up on whichever screens use it — so
 * staleness is judged against the union, in the final test, not per screen.
 */
const observed: ContrastFinding[] = [];

for (const theme of THEMES) {
  for (const screen of SCREENS) {
    test(`${screen} has no unlisted contrast pair in the ${theme} theme`, async ({ page, request }) => {
      await resetRepository(request);
      await seedOutcomes(request, [OUTCOME]);
      await setTheme(page, theme);
      await installWalker(page);
      await goto(page, screen);

      const results = await new AxeBuilder({ page }).withRules(["color-contrast"]).analyze();
      expect(
        results.violations.map(
          (violation) =>
            `screen=${screen} theme=${theme} rule=${violation.id} ` +
            `selectors=${violation.nodes.map((node) => node.target.join(" ")).join(", ")}`,
        ),
      ).toEqual([]);

      const findings = await page.evaluate(
        ([name, value]) => window.__odiContrastScan(document.body, name, value),
        [screen, theme] as const,
      );
      observed.push(...findings);

      expect(formatFindings(unlistedFindings(findings, KNOWN_PAIRS))).toBe("");
    });
  }
}

test("every known pair still fails, so the list can only shrink", () => {
  // A pair on the list that no longer fails is stale: it must be removed, or
  // the list stops meaning "these are the failures we still owe".
  expect(
    staleKnownPairs(KNOWN_PAIRS, observed).map((entry) => `#${entry.issue} ${entry.note}`),
  ).toEqual([]);
});

test("the gate fails on a deliberately low-contrast class", async ({ page, request }) => {
  await resetRepository(request);
  await installWalker(page);
  await openStudio(page);

  const findings = await page.evaluate(() => {
    const style = document.createElement("style");
    style.textContent =
      ".deliberately-unreadable { color: #9aa0aa; background-color: #a2a7b3; }";
    document.head.appendChild(style);
    const bad = document.createElement("p");
    bad.className = "deliberately-unreadable";
    bad.textContent = "Deliberately unreadable caption";
    document.body.appendChild(bad);
    return window.__odiContrastScan(document.body, "injected", "dark");
  });

  expect(
    unlistedFindings(findings, KNOWN_PAIRS).some((finding) =>
      finding.selector.includes("deliberately-unreadable"),
    ),
  ).toBe(true);
  expect(formatFindings(findings)).toContain("screen=injected");
});
