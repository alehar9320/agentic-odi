import { expect, test } from "./fixtures";

import { banners, offlineNotice, openStudio, rail } from "./helpers";

/**
 * Capturing an outcome by hand is the promise the Studio makes when no model
 * is reachable: the user can still record a job, score an outcome, and see it
 * land in the canvas.
 *
 * The whole journey crosses every layer — the SPA, the sidecar, and the
 * repository — so it is the test that would catch a seam breaking.
 */
test.describe("capturing an outcome", () => {
  test("records an outcome and shows it in the landscape", async ({ page }) => {
    await openStudio(page);

    // The offline notice offers a way into the capture panel.
    await offlineNotice(page).getByRole("button", { name: "Capture an outcome" }).click();

    const panel = page.getByRole("complementary", { name: "Add what you heard" });
    await expect(panel).toBeVisible();

    // A job first: an outcome is always a metric for a job.
    await panel.getByLabel("Job name").fill("Ship a service to production");
    await panel.getByRole("button", { name: "Add job" }).click();
    await expect(banners(page).filter({ hasText: "Job created" })).toBeVisible();

    // Then the outcome itself.
    await panel
      .getByLabel("Desired outcome")
      .fill("Minimize the time to deploy a service when releasing a hotfix");
    await panel.getByRole("button", { name: "Record outcome" }).click();
    await expect(banners(page).filter({ hasText: "Outcome captured" })).toBeVisible();

    // The outcome is now part of the canvas.
    await rail(page).getByRole("button", { name: /^Where to focus,/ }).click();
    const landscape = page.getByRole("complementary", { name: "Where to focus" });
    await expect(landscape).toBeVisible();
    await expect(landscape).toContainText("Minimize the time to deploy a service");
  });

  test("recomputes the opportunity score as the sliders move", async ({ page }) => {
    await openStudio(page);
    await offlineNotice(page).getByRole("button", { name: "Capture an outcome" }).click();

    const panel = page.getByRole("complementary", { name: "Add what you heard" });
    // The preview sentence is the panel's own readout: "Opportunity 13.5
    // underserved". The regex anchors both numbers, so "13.50" cannot pass as
    // "13.5" the way a substring check would.
    const score = panel.getByText(/^Opportunity\s/).first();

    // importance 8.5, satisfaction 3.5 -> 8.5 + max(8.5 - 3.5, 0) = 13.5.
    await expect(score).toHaveText(/Opportunity\s*13\.5\s*underserved/);

    await panel.getByLabel(/^Importance/).fill("9.2");

    // 9.2 + max(9.2 - 3.5, 0) = 14.9
    await expect(score).toHaveText(/Opportunity\s*14\.9\s*underserved/);
    // The slider and the label the user reads both follow.
    await expect(panel.getByLabel(/^Importance/)).toHaveValue("9.2");
    await expect(panel.getByText("Importance · 9.2")).toBeVisible();
  });

  test("marks a low-importance outcome as appropriately served", async ({ page }) => {
    await openStudio(page);
    await offlineNotice(page).getByRole("button", { name: "Capture an outcome" }).click();

    const panel = page.getByRole("complementary", { name: "Add what you heard" });
    await panel.getByLabel(/^Importance/).fill("4");
    await panel.getByLabel(/^Current satisfaction/).fill("9");

    // 4 + max(4 - 9, 0) = 4.0, which is not underserved.
    const score = panel.getByText(/^Opportunity\s/).first();
    await expect(score).toHaveText(/Opportunity\s*4\.0\s*appropriately served/);
  });

  test("will not record an outcome without a statement", async ({ page }) => {
    await openStudio(page);
    await offlineNotice(page).getByRole("button", { name: "Capture an outcome" }).click();

    const panel = page.getByRole("complementary", { name: "Add what you heard" });
    // An outcome always belongs to a job, so the repository starts empty here.
    await panel.getByLabel("Job name").fill("Ship a service to production");
    await panel.getByRole("button", { name: "Add job" }).click();
    await expect(banners(page).filter({ hasText: "Job created" })).toBeVisible();

    await expect(panel.getByRole("button", { name: "Record outcome" })).toBeDisabled();

    await panel.getByLabel("Desired outcome").fill("Minimize the wait");
    await expect(panel.getByRole("button", { name: "Record outcome" })).toBeEnabled();
  });
});
