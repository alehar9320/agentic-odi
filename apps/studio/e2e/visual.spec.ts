import { expect, test } from "@playwright/test";

import { openBrief, openLandscape, seedSampleCanvas, setTheme } from "./visual/fixtures";

/**
 * The screen-level visual harness (issue #547).
 *
 * One deterministic fixture seeds a job, three scored outcomes (one
 * unscored, one underserved, one served), two steps, and two evidence quotes
 * — every row labelled as sample data, so the canvas is marked as a seed
 * prototype and the provenance chip renders "DEMO" rather than the fixture
 * passing itself off as a user's work. Chromatic covers components; this suite
 * covers the assembled screen, in both themes and at two viewports.
 *
 * Nothing here asserts correctness: the harness exists so a human can look at
 * a screen the CI job posts on every PR. A capture failure must not turn the
 * run red, so the assertions are `toHaveScreenshot` only.
 *
 * The clock is pinned by the fixed fixture data and reduced motion collapses
 * animations to their end state, which `theme.css` honors, so the page is
 * measured at rest and a second run is byte-identical.
 */
const LANDSCAPE = "landscape";

test.describe("the screen-level visual harness", () => {
  test("landscape · dark theme · 1280×800", async ({ page, request }) => {
    await setTheme(page, "dark");
    await seedSampleCanvas(page, request);
    await openLandscape(page);
    await expect(page.getByRole("complementary", { name: "Opportunity landscape" })).toBeVisible();
    await page.waitForFunction(() => document.fonts.ready);
    await expect(page.locator("html")).toHaveClass(/theme-dark/);
    await expect(page.getByRole("main")).toBeVisible();
    await expect(page).toHaveScreenshot(`${LANDSCAPE}-dark-1280.png`, {
      maxDiffPixelRatio: 0,
      animations: "disabled",
      caret: "hide",
      fullPage: true,
    });
  });

  test("landscape · light theme · 1280×800", async ({ page, request }) => {
    await setTheme(page, "light");
    await seedSampleCanvas(page, request);
    await openLandscape(page);
    await expect(page.getByRole("complementary", { name: "Opportunity landscape" })).toBeVisible();
    await page.waitForFunction(() => document.fonts.ready);
    await expect(page.locator("html")).toHaveClass(/theme-light/);
    await expect(page.getByRole("main")).toBeVisible();
    await expect(page).toHaveScreenshot(`${LANDSCAPE}-light-1280.png`, {
      maxDiffPixelRatio: 0,
      animations: "disabled",
      caret: "hide",
      fullPage: true,
    });
  });

  test("landscape · dark theme · 390×844", async ({ page, request }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await setTheme(page, "dark");
    await seedSampleCanvas(page, request);
    await openLandscape(page);
    await expect(page.getByRole("complementary", { name: "Opportunity landscape" })).toBeVisible();
    await page.waitForFunction(() => document.fonts.ready);
    await expect(page.locator("html")).toHaveClass(/theme-dark/);
    await expect(page.getByRole("main")).toBeVisible();
    await expect(page).toHaveScreenshot(`${LANDSCAPE}-dark-390.png`, {
      maxDiffPixelRatio: 0,
      animations: "disabled",
      caret: "hide",
      fullPage: true,
    });
  });

  test("landscape · light theme · 390×844", async ({ page, request }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await setTheme(page, "light");
    await seedSampleCanvas(page, request);
    await openLandscape(page);
    await expect(page.getByRole("complementary", { name: "Opportunity landscape" })).toBeVisible();
    await page.waitForFunction(() => document.fonts.ready);
    await expect(page.locator("html")).toHaveClass(/theme-light/);
    await expect(page.getByRole("main")).toBeVisible();
    await expect(page).toHaveScreenshot(`${LANDSCAPE}-light-390.png`, {
      maxDiffPixelRatio: 0,
      animations: "disabled",
      caret: "hide",
      fullPage: true,
    });
  });

  test("brief · dark theme · 1280×800", async ({ page, request }) => {
    await setTheme(page, "dark");
    await seedSampleCanvas(page, request);
    await openBrief(page);
    await expect(page.getByRole("article", { name: "Decision brief" })).toContainText(
      "Minimize the time to deploy a service",
    );
    await page.waitForFunction(() => document.fonts.ready);
    await expect(page.locator("html")).toHaveClass(/theme-dark/);
    await expect(page).toHaveScreenshot(`brief-dark-1280.png`, {
      maxDiffPixelRatio: 0,
      animations: "disabled",
      caret: "hide",
      fullPage: true,
    });
  });
});