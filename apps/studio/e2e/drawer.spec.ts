import { expect, test } from "@playwright/test";

import { COMPOSER, openStudio, rail } from "./helpers";

/**
 * The drawer is the identity of the shell (#736): the brand, the one way to
 * start, the threads you have open, and who you are. These tests cover the
 * contract the issue names — and the flag that brings the old shell back.
 */
test.describe("the navigation drawer", () => {
  test("carries the brand, one way to start, and the identity chip", async ({ page }) => {
    await openStudio(page);

    const drawer = rail(page);
    await expect(drawer).toBeVisible();
    await expect(
      drawer.getByRole("button", { name: /Living Studio, go to home/i }),
    ).toBeVisible();
    await expect(drawer.getByRole("button", { name: /new inquiry/i })).toBeVisible();
    await expect(drawer.getByRole("heading", { name: "Recent threads" })).toBeVisible();
    await expect(drawer.getByRole("button", { name: "Identity options" })).toBeVisible();
  });

  test("collapses and remembers the choice across a reload", async ({ page }) => {
    await openStudio(page);
    await expect(rail(page)).toBeVisible();

    await page.getByRole("button", { name: "Hide navigation" }).click();
    await expect(rail(page)).toBeHidden();

    await page.reload();
    await expect(page.getByRole("textbox", { name: COMPOSER })).toBeVisible();
    await expect(rail(page)).toBeHidden();

    await page.getByRole("button", { name: "Show navigation" }).click();
    await expect(rail(page)).toBeVisible();
  });

  test("New inquiry hands the caret back to the composer", async ({ page }) => {
    await openStudio(page);

    await rail(page).getByRole("button", { name: /new inquiry/i }).click();

    await expect(page.getByRole("textbox", { name: COMPOSER })).toBeFocused();
  });

  test("the job map is a drawer destination", async ({ page }) => {
    await openStudio(page);

    await rail(page).getByRole("button", { name: "Job map" }).click();

    await expect(
      page.getByRole("complementary", { name: "Universal job map" }),
    ).toBeVisible();
  });

  test("Escape backs out of the detail, then the drawer", async ({ page }) => {
    await openStudio(page);
    await rail(page).getByRole("button", { name: "Job map" }).click();
    await expect(
      page.getByRole("complementary", { name: "Universal job map" }),
    ).toBeVisible();

    await page.keyboard.press("Escape");
    await expect(
      page.getByRole("complementary", { name: "Universal job map" }),
    ).toBeHidden();
    await expect(rail(page)).toBeVisible();

    await page.keyboard.press("Escape");
    await expect(rail(page)).toBeHidden();
  });

  test("Meta/Ctrl+K opens Quick jump, whose first row returns the caret", async ({ page }) => {
    await openStudio(page);

    await page.keyboard.press("Control+k");

    const dialog = page.getByRole("dialog", { name: "Quick jump" });
    await expect(dialog).toBeVisible();
    const first = dialog.getByRole("option").first();
    await expect(first).toContainText("New inquiry");

    await first.click();
    await expect(page.getByRole("textbox", { name: COMPOSER })).toBeFocused();
  });

  test("the off flag renders the shell the drawer replaced", async ({ page }) => {
    await page.addInitScript(() => {
      window.localStorage.setItem("studio.setupDismissed", "1");
    });
    await page.goto("/?flags=firstRunWizard:off,studioDrawer:off");

    await expect(page.getByRole("textbox", { name: COMPOSER })).toBeVisible();
    await expect(
      page.getByRole("banner").getByRole("button", { name: /go to home/i }),
    ).toBeVisible();
    await expect(rail(page)).toBeHidden();
  });
});
