import { test } from "@playwright/test";

import { COMPOSER, lastReply, openStudio, rail, resetRepository, seedOutcomes } from "./helpers";

/**
 * Product screenshots for pull-request review.
 *
 * This spec is not part of the regular `test:e2e` run — it is invoked
 * explicitly by `.github/workflows/pr-screenshots.yml` — because it exists to
 * show a reviewer the running product, not to assert on it. It drives the
 * existing `playwright.config.ts` `webServer` (MCP on `:8000`, sidecar on
 * `:8100`, serving the built SPA from `apps/studio/dist`) exactly like the
 * `e2e` suite, and it captures six key screens into `apps/studio/pr-screenshots/`
 * with deterministic names.
 *
 * Nothing here asserts correctness: a capture that fails is reported, and the
 * workflow's `continue-on-error: true` keeps CI green. Screenshots are for
 * human review only — there are no baselines, diffs, or visual assertions.
 */

const SCREENSHOT_DIR = "pr-screenshots";

const OUTCOME = {
  statement: "Minimize the time to deploy a service when releasing a hotfix",
  importance: 9.2,
  satisfaction: 3.1,
};

test.beforeEach(async ({ request }) => {
  await resetRepository(request);
});

test("captures the six key screens", async ({ page, request }) => {
  await seedOutcomes(request, [OUTCOME]);
  await openStudio(page);

  // 1. Home — the first paint, before anything is clicked.
  await page.screenshot({
    path: `${SCREENSHOT_DIR}/01-home.png`,
    fullPage: true,
  });

  // 2. Chat — one message in, reply landed.
  await page.getByRole("textbox", { name: COMPOSER }).fill(
    "Walk me through the ODI stage-by-stage guidelines.",
  );
  await page.getByRole("button", { name: "Send message" }).click();
  await lastReply(page);
  await page.screenshot({
    path: `${SCREENSHOT_DIR}/02-chat.png`,
    fullPage: true,
  });

  // 3. Job map — a rail panel with real content behind it.
  await rail(page).getByRole("button", { name: /^Job map,/ }).click();
  await page.screenshot({
    path: `${SCREENSHOT_DIR}/03-job-map.png`,
    fullPage: true,
  });

  // 4. Landscape — the scored outcomes a brief is written from.
  await rail(page).getByRole("button", { name: /^Landscape,/ }).click();
  await page.screenshot({
    path: `${SCREENSHOT_DIR}/04-landscape.png`,
    fullPage: true,
  });

  // 5. Segments — the grouping of outcomes into named segments.
  await rail(page).getByRole("button", { name: /^Segments,/ }).click();
  await page.screenshot({
    path: `${SCREENSHOT_DIR}/05-segments.png`,
    fullPage: true,
  });

  // 6. Brief — the decision brief document a reviewer reads.
  await page.getByRole("textbox", { name: COMPOSER }).fill("/brief");
  await page.keyboard.press("Enter");
  await page.screenshot({
    path: `${SCREENSHOT_DIR}/06-brief.png`,
    fullPage: true,
  });
});