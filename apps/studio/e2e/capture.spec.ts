import { expect, test } from "@playwright/test";

import { offlineNotice, openStudio, rail, resetRepository } from "./helpers";

/**
 * Capturing an outcome by hand is the promise the Studio makes when no model
 * is reachable: the user can still record a job, score an outcome, and see it
 * land in the canvas.
 *
 * The whole journey crosses every layer — the SPA, the sidecar, and the
 * repository — so it is the test that would catch a seam breaking.
 */
test.describe("capturing an outcome", () => {
  test.beforeEach(async ({ request }) => {
    // The sidecar repository is shared by the whole run, so a retry or a later
    // test must not inherit the job the previous attempt already created.
    await resetRepository(request);
  });

  test("records an outcome and shows it in the landscape", async ({ page }) => {
    await openStudio(page);

    // The offline notice offers a way into the capture panel.
    await offlineNotice(page).getByRole("button", { name: "Capture an outcome" }).click();

    const panel = page.getByRole("complementary", { name: "Capture by hand" });
    await expect(panel).toBeVisible();

    // A job first: an outcome is always a metric for a job.
    await panel.getByLabel("Job name").fill("Ship a service to production");
    await panel.getByRole("button", { name: "Add job" }).click();
    await expect(page.locator(".banner").filter({ hasText: "Job created" })).toBeVisible();

    // Then the outcome itself.
    await panel
      .getByLabel("Desired outcome")
      .fill("Minimize the time to deploy a service when releasing a hotfix");
    await panel.getByRole("button", { name: "Record outcome" }).click();
    await expect(page.locator(".banner").filter({ hasText: "Outcome captured" })).toBeVisible();

    // The outcome is now part of the canvas.
    await rail(page).getByRole("button", { name: /^Landscape,/ }).click();
    const landscape = page.getByRole("complementary", { name: "Opportunity landscape" });
    await expect(landscape).toBeVisible();
    await expect(landscape).toContainText("Minimize the time to deploy a service");
  });

  test("recomputes the opportunity score as the sliders move", async ({ page }) => {
    await openStudio(page);
    await offlineNotice(page).getByRole("button", { name: "Capture an outcome" }).click();

    const panel = page.getByRole("complementary", { name: "Capture by hand" });
    const score = panel.locator(".score-preview");

    // importance 8.5, satisfaction 3.5 -> 8.5 + max(8.5 - 3.5, 0) = 13.50
    await expect(score).toContainText("13.50");
    await expect(score).toContainText("underserved");

    await panel.getByLabel(/^Importance/).fill("9.2");

    // 9.2 + max(9.2 - 3.5, 0) = 14.90
    await expect(score).toContainText("14.90");
    // The slider and the label the user reads both follow.
    await expect(panel.getByLabel(/^Importance/)).toHaveValue("9.2");
    await expect(panel.getByText("Importance · 9.2")).toBeVisible();
  });

  test("marks a low-importance outcome as appropriately served", async ({ page }) => {
    await openStudio(page);
    await offlineNotice(page).getByRole("button", { name: "Capture an outcome" }).click();

    const panel = page.getByRole("complementary", { name: "Capture by hand" });
    await panel.getByLabel(/^Importance/).fill("4");
    await panel.getByLabel(/^Current satisfaction/).fill("9");

    // 4 + max(4 - 9, 0) = 4.00, which is not underserved.
    await expect(panel.locator(".score-preview")).toContainText("4.00");
    await expect(panel.locator(".score-preview")).toContainText("appropriately served");
  });

  test("will not record an outcome without a statement", async ({ page }) => {
    await openStudio(page);
    await offlineNotice(page).getByRole("button", { name: "Capture an outcome" }).click();

    const panel = page.getByRole("complementary", { name: "Capture by hand" });
    // An outcome always belongs to a job, so the repository starts empty here.
    await panel.getByLabel("Job name").fill("Ship a service to production");
    await panel.getByRole("button", { name: "Add job" }).click();
    await expect(page.locator(".banner").filter({ hasText: "Job created" })).toBeVisible();

    await expect(panel.getByRole("button", { name: "Record outcome" })).toBeDisabled();

    await panel.getByLabel("Desired outcome").fill("Minimize the wait");
    await expect(panel.getByRole("button", { name: "Record outcome" })).toBeEnabled();
  });
});
