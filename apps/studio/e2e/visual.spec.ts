import { expect, test, type Page } from "@playwright/test";

import { openStudio, resetConversations, workbench } from "./helpers";
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
 * Pin the system faces to the Liberation fonts Playwright installs on CI.
 *
 * The display face is already self-hosted; leaving the sans and mono faces to
 * the host makes the same screen differ between a laptop and the runner. This
 * has to run after navigation, or it would style the blank page instead.
 */
async function pinFonts(page: Page): Promise<void> {
  await page.evaluate(() => {
    // The page's CSP refuses an inline <style>; setting the custom properties
    // through the CSSOM is not an inline style parse and is allowed.
    document.documentElement.style.setProperty(
      "--font",
      '"Liberation Sans", Arial, sans-serif',
      "important",
    );
    document.documentElement.style.setProperty(
      "--mono",
      '"Liberation Mono", monospace',
      "important",
    );
  });
}

/**
 * Replace the ids the sidecar assigns at random with one stable placeholder.
 *
 * The placeholder keeps the 36-character shape, so the tables wrap exactly as
 * they would with a real id, while two runs can never disagree on which hex
 * letters fall on a line. Without this, every screenshot is a different image
 * even though the store, the layout, and the values around the ids are the same.
 */
async function normalizeIds(page: Page): Promise<void> {
  await page.evaluate(() => {
    const uuid = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi;
    const placeholder = "00000000-0000-4000-8000-000000000000";
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    const texts: Text[] = [];
    while (walker.nextNode()) {
      texts.push(walker.currentNode as Text);
    }
    for (const node of texts) {
      node.data = node.data.replace(uuid, placeholder);
    }
  });
}

/**
 * Open the Studio on a fresh canvas and open the named view. The first-run
 * wizard and the setup conversation are switched off the way a QA engineer
 * would, so the screen under test is the only thing on screen.
 */
async function openView(page: Page, view: string): Promise<void> {
  await openStudio(page);
  await workbench(page)
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
    await resetConversations(request);
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

        // The same lens is docked (complementary) on desktop and a dialog
        // sheet on mobile; the class is the surface both shells share.
        await expect(page.locator(".lens").first()).toBeVisible();
        await expect(page.getByText("On-call incident report")).toBeVisible();

        await pinFonts(page);
        await normalizeIds(page);

        await expect(page).toHaveScreenshot(`records-${viewport.name}-${theme}.png`, {
          maxDiffPixelRatio: 0.01,
        });
      });

      test(`renders the landscape at ${viewport.name} in ${theme} theme`, async ({
        page,
        request,
      }) => {
        await seedCanvas(request, MULTI_JOB);
        await emulateTheme(page, theme);
        await page.setViewportSize({ width: viewport.width, height: viewport.height });

        await openView(page, "Landscape");

        await expect(page.locator(".lens").first()).toBeVisible();
        await pinFonts(page);
        await normalizeIds(page);

        await expect(page).toHaveScreenshot(`landscape-${viewport.name}-${theme}.png`, {
          maxDiffPixelRatio: 0.01,
        });
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

        await expect(page.locator(".lens").first()).toBeVisible();
        await pinFonts(page);
        await normalizeIds(page);

        await expect(page).toHaveScreenshot(`capture-${viewport.name}-${theme}.png`, {
          maxDiffPixelRatio: 0.01,
        });
      });
    }
  }
});