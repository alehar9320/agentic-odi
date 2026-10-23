import { expect, test } from "@playwright/test";

import { lens, offlineNotice, openStudio, rail, resetRepository, seedOutcomes } from "./helpers";

/**
 * The Studio is a single surface with views that open beside the
 * conversation. These tests cover opening a view, that it is announced
 * correctly to assistive technology, and that it closes again.
 */
const OUTCOME = {
  statement: "Minimize the time to deploy a service",
  importance: 9.2,
  satisfaction: 3.1,
};

test.describe("the workspace", () => {
  test.beforeEach(async ({ request }) => {
    await resetRepository(request);
  });

  test("opens a view from the workbench rail", async ({ page, request }) => {
    await seedOutcomes(request, [OUTCOME]);
    await openStudio(page);

    // The rail only appears once there is something to look at.
    const landscape = rail(page).getByRole("button", { name: /^Landscape,/ });
    await expect(landscape).toBeVisible();

    await landscape.click();
    await expect(lens(page)).toHaveAttribute("aria-label", "Opportunity landscape");
  });

  test("marks the open view as current", async ({ page, request }) => {
    await seedOutcomes(request, [OUTCOME]);
    await openStudio(page);

    const landscape = rail(page).getByRole("button", { name: /^Landscape,/ });
    await expect(landscape).not.toHaveAttribute("aria-current", "page");

    await landscape.click();
    await expect(landscape).toHaveAttribute("aria-current", "page");
  });

  test("closes the open view", async ({ page, request }) => {
    await seedOutcomes(request, [OUTCOME]);
    await openStudio(page);

    await rail(page).getByRole("button", { name: /^Landscape,/ }).click();
    await expect(lens(page)).toBeVisible();

    await page.getByRole("button", { name: "Close workspace view" }).click();
    await expect(lens(page)).toBeHidden();
  });

  test("closes the open view with Escape", async ({ page, request }) => {
    await seedOutcomes(request, [OUTCOME]);
    await openStudio(page);

    await rail(page).getByRole("button", { name: /^Landscape,/ }).click();
    await expect(lens(page)).toBeVisible();

    await page.keyboard.press("Escape");
    await expect(lens(page)).toBeHidden();
  });

  test("offers a way into the settings", async ({ page }) => {
    await openStudio(page);

    await page.getByRole("button", { name: "Open settings" }).click();

    await expect(lens(page)).toHaveAttribute("aria-label", "Settings");
    await expect(lens(page).getByLabel("MCP server URL")).toBeVisible();
  });

  test("says so when no model is reachable", async ({ page }) => {
    await openStudio(page);

    // No model is reachable during the test run, so the bar says so.
    await expect(page.getByRole("button", { name: "Local mode" })).toBeVisible();
    await expect(offlineNotice(page)).toBeVisible();
  });
});
