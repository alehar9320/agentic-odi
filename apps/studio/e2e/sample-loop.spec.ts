import { expect, test } from "@playwright/test";

import { COMPOSER, openStudio } from "./helpers";

/**
 * The empty stage's worked example (#318).
 *
 * A person who has never seen the ODI loop run meets one finished pass before
 * they produce anything: the quote, the outcome, the score, and the gap, all
 * labelled a sample. These tests assert the label is visible before any
 * interaction, that the hand-off writes nothing, and that Hide survives a
 * reload.
 */
test.describe("the sample loop", () => {
  test("shows a labelled finished loop before any interaction", async ({ page }) => {
    await openStudio(page);

    const strip = page.getByRole("region", { name: "Sample loop, not your data" });
    await expect(strip).toBeVisible();
    await expect(strip.getByText("Sample, not your data.")).toBeVisible();
    await expect(strip.getByText("SAMPLE", { exact: true })).toBeVisible();

    // The three beats: the quote and its hypothetical source, the outcome with
    // its two numbers and derived score, and the gap.
    await expect(strip).toContainText("I keep a spreadsheet of config keys");
    await expect(strip).toContainText("hypothetical onboarding call");
    await expect(strip).toContainText("Opportunity");
    await expect(strip.getByText("Underserved")).toBeVisible();
    await expect(strip.getByText("What's missing")).toBeVisible();
    await expect(strip).toContainText("one customer only");
    await expect(strip).toContainText("no linked job step");
    await expect(strip).toContainText("no second source");
  });

  test("hands the composer focus without sending anything", async ({ page }) => {
    await openStudio(page);

    await page.getByRole("button", { name: "Start with my own" }).click();

    const composer = page.getByRole("textbox", { name: COMPOSER });
    await expect(composer).toBeFocused();
    await expect(composer).toHaveAttribute("placeholder", "Paste a customer quote to begin.");
    await expect(composer).toHaveValue("");
    // Nothing was sent, so the thread is still empty.
    await expect(page.getByRole("log", { name: "Conversation" })).toHaveCount(0);
  });

  test("hides the sample and survives a reload", async ({ page }) => {
    await openStudio(page);

    await page.getByRole("button", { name: "Hide" }).click();

    const strip = page.getByRole("region", { name: "Sample loop, not your data" });
    await expect(strip).toHaveCount(0);

    await page.reload();
    await expect(page.getByRole("textbox", { name: COMPOSER })).toBeVisible();
    await expect(strip).toHaveCount(0);
  });
});
