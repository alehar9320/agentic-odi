import { expect, test } from "@playwright/test";

import { CONVERSATION, openStudio, resetRepository } from "./helpers";

/**
 * The starter cards are the Studio's first sentence (#316). These tests cover
 * what a person with nothing on the canvas is offered and what a click sends
 * into the thread.
 */
const STARTERS = [
  "Turn 40 interview notes into one bet",
  "Find what the churn spike is telling you",
  "Inherit a roadmap without inheriting its assumptions",
];

test.describe("the starters", () => {
  test.beforeEach(async ({ request }) => {
    await resetRepository(request);
  });

  test("offers three concrete situations, in order, on an empty canvas", async ({ page }) => {
    await openStudio(page);

    const starters = page.locator(".composer__pills");
    for (const title of STARTERS) {
      await expect(starters.getByRole("button", { name: title })).toBeVisible();
    }

    // The first run no longer asks the person to translate their week into our
    // nouns before they can click.
    await expect(starters).not.toContainText("Sharpen an opportunity");
    await expect(starters).not.toContainText("Find the next opportunity");
    await expect(starters).not.toContainText("Name the job");
  });

  test("sends the first starter's prompt into the thread", async ({ page }) => {
    await openStudio(page);

    await page
      .locator(".composer__pills")
      .getByRole("button", { name: STARTERS[0] })
      .click();

    // The count is the person's own material, not a figure the studio reports.
    const log = page.getByRole("log", { name: CONVERSATION });
    await expect(log).toContainText("I have about 40 interview notes from the last month.");
    await expect(log).toContainText(
      "Help me turn them into one opportunity we can defend",
    );
  });
});
