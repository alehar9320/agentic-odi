import { expect, test, type Page } from "@playwright/test";

import { COMPOSER, lens, openStudio, resetRepository, seedOutcomes } from "./helpers";

/**
 * The decision brief is the document the studio writes for a review, and it is
 * the one surface whose contract is about paper: what a reader sees when they
 * press Print has to be the document, not the app. Playwright can emulate the
 * print media, which is what neither jsdom nor a unit test can check.
 *
 * `window.print` is replaced with a no-op because the print dialog is modal and
 * would block the run; marking the body is the half the stylesheet depends on.
 */
const OUTCOME = {
  statement: "Minimize the time to deploy a service when releasing a hotfix",
  importance: 9.2,
  satisfaction: 3.1,
};

const DOCUMENT = "Decision brief";

test.describe("the decision brief", () => {
  test.beforeEach(async ({ request }) => {
    await resetRepository(request);
  });

  test("opens from the landscape header", async ({ page, request }) => {
    await seedOutcomes(request, [OUTCOME]);
    await openStudio(page);

    await railLandscape(page).click();
    await page.getByRole("button", { name: "Export brief" }).click();

    await expect(lens(page)).toHaveAttribute("aria-label", DOCUMENT);
    await expect(lens(page).getByRole("article", { name: DOCUMENT })).toContainText(
      "Minimize the time to deploy",
    );
  });

  test("opens with the slash command, without a model", async ({ page, request }) => {
    await seedOutcomes(request, [OUTCOME]);
    await openStudio(page);

    await page.getByRole("textbox", { name: COMPOSER }).fill("/brief");
    await page.keyboard.press("Enter");

    await expect(lens(page)).toHaveAttribute("aria-label", DOCUMENT);
  });

  test("is not offered before there is anything to brief", async ({ page }) => {
    await openStudio(page);

    await page.getByRole("textbox", { name: COMPOSER }).fill("/landscape");
    await page.keyboard.press("Enter");

    const exportBrief = page.getByRole("button", { name: "Export brief" });
    await expect(exportBrief).toBeDisabled();
    await expect(exportBrief).toHaveAttribute("title", "Nothing to brief yet");
  });

  test("prints the document and nothing else", async ({ page, request }) => {
    await seedOutcomes(request, [OUTCOME]);
    await page.addInitScript(() => {
      window.print = () => {};
    });
    await openStudio(page);

    await page.getByRole("textbox", { name: COMPOSER }).fill("/brief");
    await page.keyboard.press("Enter");
    await lens(page).getByRole("button", { name: "Print / PDF" }).click();
    await expect(page.locator("body")).toHaveClass(/brief-printing/);

    await page.emulateMedia({ media: "print" });
    await expect(lens(page).getByRole("article", { name: DOCUMENT })).toBeVisible();
    await expect(page.locator(".brief__bar")).toBeHidden();
    await expect(lens(page).getByRole("textbox", { name: /What argues against/ })).toBeHidden();
    await expect(page.getByRole("textbox", { name: COMPOSER })).toBeHidden();
    await expect(page.locator(".chat")).toBeHidden();
  });

  test("carries an objection typed on the sheet into the document", async ({
    page,
    request,
  }) => {
    await seedOutcomes(request, [OUTCOME]);
    await openStudio(page);

    await page.getByRole("textbox", { name: COMPOSER }).fill("/brief");
    await page.keyboard.press("Enter");

    await lens(page)
      .getByRole("textbox", { name: "What argues against this?" })
      .fill("Release cadence is already a solved problem for this buyer.");

    await expect(lens(page).getByRole("article", { name: DOCUMENT })).toContainText(
      "Release cadence is already a solved problem",
    );
    await expect(lens(page).getByRole("article", { name: DOCUMENT })).toContainText(
      "author-supplied",
    );
  });
});

/** The landscape chip in the workbench rail. */
function railLandscape(page: Page) {
  return page
    .getByRole("navigation", { name: "Your work" })
    .getByRole("button", { name: /^Where to focus,/ });
}
