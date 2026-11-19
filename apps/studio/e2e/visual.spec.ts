import { expect, test, type Page } from "@playwright/test";

import { openStudio, rail } from "./helpers";
import { MULTI_JOB, RECORD_JOB, seedCanvas } from "./visual/fixtures";

/**
 * The visual harness: a deterministic set of screens, rendered at two sizes and
 * in both themes, with fonts and animation disabled.
 *
 * Every fixture is seeded through the API by hand — no model, no randomness —
 * so the pixels are the same on every run. The spec is a screenshot contract:
 * it records what the Studio looks like and fails when the rendering changes.
 *
 * Run it with `playwright test --project=visual` and review the diffs in
 * `e2e/__screenshots__/visual.spec.ts-snapshots/`.
 */
const VIEWPORTS = [
  { name: "desktop", width: 1280, height: 800 },
  { name: "mobile", width: 390, height: 844 },
];

const THEMES = ["dark", "light"] as const;

/** Emulate the theme and reduce motion so a transition cannot differ between runs. */
function emulateTheme(page: Page, theme: "dark" | "light") {
  return page.emulateMedia({ colorScheme: theme, reducedMotion: "reduce" });
}

/**
 * Open the Studio on a fresh canvas and open the named view. The first-run
 * wizard and the setup conversation are switched off the way a QA engineer
 * would, so the screen under test is the only thing on screen.
 */
async function openView(page: Page, view: string): Promise<void> {
  await openStudio(page);
  await rail(page)
    .getByRole("button", { name: new RegExp(`^${view},`) })
    .click();
}

test.describe("the visual harness", () => {
  test.beforeEach(async ({ request }) => {
    // The sidecar repository is shared by the whole run, so every screen
    // starts from the empty canvas the way a first visit does.
    const canvas = await request.get("/api/canvas");
    expect(canvas.ok()).toBeTruthy();
    const body = (await canvas.json()) as { jobs: { id: string }[] };
    for (const job of body.jobs) {
      const deleted = await request.delete(`/api/jobs/${encodeURIComponent(job.id)}`);
      expect(deleted.ok()).toBeTruthy();
    }
  });

  for (const viewport of VIEWPORTS) {
    for (const theme of THEMES) {
      test(`renders the records view at ${viewport.name} in ${theme} theme`, async ({
        page,
        request,
      }) => {
        await seedCanvas(request, RECORD_JOB);
        await emulateTheme(page, theme);
        await page.setViewportSize({ width: viewport.width, height: viewport.height });

        await openView(page, "Records");

        await expect(page.getByRole("complementary", { name: "Records" })).toBeVisible();
        await expect(page.getByText("On-call incident report")).toBeVisible();

        await expect(page).toHaveScreenshot(
          `records-${viewport.name}-${theme}.png`,
        );
      });

      test(`renders the landscape at ${viewport.name} in ${theme} theme`, async ({
        page,
        request,
      }) => {
        await seedCanvas(request, MULTI_JOB);
        await emulateTheme(page, theme);
        await page.setViewportSize({ width: viewport.width, height: viewport.height });

        await openView(page, "Landscape");

        await expect(
          page.getByRole("complementary", { name: "Opportunity landscape" }),
        ).toBeVisible();

        await expect(page).toHaveScreenshot(
          `landscape-${viewport.name}-${theme}.png`,
        );
      });

      test(`renders the capture panel at ${viewport.name} in ${theme} theme`, async ({
        page,
        request,
      }) => {
        await seedCanvas(request, RECORD_JOB);
        await emulateTheme(page, theme);
        await page.setViewportSize({ width: viewport.width, height: viewport.height });

        await openStudio(page);
        await page
          .locator(".banner")
          .filter({ hasText: "Working by hand" })
          .getByRole("button", { name: "Capture an outcome" })
          .click();

        await expect(
          page.getByRole("complementary", { name: "Capture by hand" }),
        ).toBeVisible();

        await expect(page).toHaveScreenshot(
          `capture-${viewport.name}-${theme}.png`,
        );
      });
    }
  }
});