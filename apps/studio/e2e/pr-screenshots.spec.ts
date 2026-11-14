import { expect, test, type Page } from "@playwright/test";

import { openStudio, rail, resetRepository, seedOutcomes, sendMessage } from "./helpers";

/**
 * Advisory screenshots of the running product for pull request review.
 *
 * This spec drives the real Studio against the real sidecar and MCP server
 * through the shared Playwright config (sidecar on 127.0.0.1:8100). It
 * asserts nothing about correctness — captures are best-effort so the
 * workflow's continue-on-error safety net never turns a screenshot miss
 * into a merge blocker.
 *
 * Run explicitly: `npx playwright test pr-screenshots.spec.ts`
 */
const OUTCOME = {
  statement: "Minimize the time to deploy a service when releasing a hotfix",
  importance: 9.2,
  satisfaction: 3.1,
};

const SCREENS_DIR = "pr-screenshots";

async function capture(page: Page, name: string): Promise<void> {
  await page.screenshot({
    path: `${SCREENS_DIR}/${name}`,
    fullPage: true,
  });
}

test.describe("PR screenshots (advisory)", () => {
  test.beforeEach(async ({ request }) => {
    await resetRepository(request);
  });

  test("captures key screens of the running Studio", async ({ page, request }) => {
    test.setTimeout(90_000);
    await seedOutcomes(request, [OUTCOME]);
    await openStudio(page);

    await capture(page, "01-home.png");

    // Chat transcript with one message rendered.
    await sendMessage(page, "Walk me through the ODI stage-by-stage guidelines.");
    await expect(
      page
        .getByRole("log", { name: "Conversation" })
        .locator(".message--assistant")
        .last()
        .getByRole("button", { name: "Copy reply" }),
    ).toBeVisible({ timeout: 20_000 });
    await capture(page, "02-chat.png");

    // Job map / workbench rail surfaces seeded content.
    await rail(page).getByRole("button", { name: /^Job map,/ }).click();
    await expect(page.getByRole("complementary").and(page.locator(".lens"))).toBeVisible();
    await capture(page, "03-job-map.png");

    await rail(page).getByRole("button", { name: /^Landscape,/ }).click();
    await expect(page.getByRole("complementary", { name: "Opportunity landscape" })).toBeVisible();
    await capture(page, "04-landscape.png");

    await rail(page).getByRole("button", { name: /^Segments,/ }).click();
    await expect(page.getByRole("complementary").and(page.locator(".lens"))).toBeVisible();
    await capture(page, "05-segments.png");

    // Brief print view (matches brief.spec.ts state).
    await page.addInitScript(() => {
      window.print = () => {};
    });
    // The init script applies on next navigation; evaluate to stub in this context too.
    await page.evaluate(() => {
      window.print = () => {};
    });
    await rail(page).getByRole("button", { name: /^Landscape,/ }).click();
    await page.getByRole("button", { name: "Export brief" }).click();
    const briefLens = page.getByRole("complementary").and(page.locator(".lens"));
    await expect(briefLens).toHaveAttribute("aria-label", "Decision brief");
    await briefLens.getByRole("button", { name: "Print / PDF" }).click();
    await expect(page.locator("body")).toHaveClass(/brief-printing/);
    await capture(page, "06-brief.png");
  });
});
