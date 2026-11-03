import { expect, test } from "@playwright/test";

import { openStudio, rail, resetRepository, seedOutcomes } from "./helpers";

/**
 * The Opportunity Landscape is where scored outcomes are read. These tests
 * cover the parts a user relies on: the headline numbers, the score pills on
 * each card, and narrowing the board by asking the store.
 */

// Statements carry an execution context ("when ..."), which the repository's
// ODI format check requires before it will store an outcome.
const UNDERSERVED = {
  statement: "Minimize the time to deploy a service when releasing a hotfix",
  importance: 9.2,
  satisfaction: 3.1,
};
const SERVED = {
  statement: "Minimize the time to rotate expired tokens when credentials leak",
  importance: 8.0,
  satisfaction: 7.2,
};

test.describe("the opportunity landscape", () => {
  test.beforeEach(async ({ request }) => {
    await resetRepository(request);
  });

  test("reports the number of jobs and outcomes", async ({ page, request }) => {
    await seedOutcomes(request, [UNDERSERVED, SERVED]);
    await openStudio(page);

    await rail(page).getByRole("button", { name: /^Landscape,/ }).click();
    const landscape = page.getByRole("complementary", { name: "Opportunity landscape" });
    await expect(landscape).toBeVisible();

    await expect(landscape.getByText("Active Job Map Contexts")).toBeVisible();
    await expect(landscape.getByText("Underserved Targets (>10)")).toBeVisible();
    await expect(landscape.getByText("Total Opportunities Analyzed")).toBeVisible();
  });

  test("labels an underserved outcome and a served one", async ({ page, request }) => {
    await seedOutcomes(request, [UNDERSERVED, SERVED]);
    await openStudio(page);

    await rail(page).getByRole("button", { name: /^Landscape,/ }).click();
    const landscape = page.getByRole("complementary", { name: "Opportunity landscape" });

    // The cards view shows every outcome, unlike the matrix, which shows one
    // at a time.
    await landscape.getByRole("button", { name: "🎴 Visual Cards" }).click();

    // 9.2 + max(9.2 - 3.1, 0) = 15.30, which is underserved.
    await expect(landscape.getByText("🔥 Underserved (Opp: 15.3)")).toBeVisible();
    // 8.0 + max(8.0 - 7.2, 0) = 8.80, which is not.
    await expect(landscape.getByText("✓ Served (Opp: 8.8)")).toBeVisible();
  });

  test("narrows the landscape by asking the store", async ({ page, request }) => {
    await seedOutcomes(request, [UNDERSERVED, SERVED]);
    await openStudio(page);

    await rail(page).getByRole("button", { name: /^Landscape,/ }).click();
    const landscape = page.getByRole("complementary", { name: "Opportunity landscape" });

    // The table view lists each outcome by statement.
    await landscape.getByRole("button", { name: "📋 Table View" }).click();
    await expect(landscape.getByText(UNDERSERVED.statement)).toBeVisible();
    await expect(landscape.getByText(SERVED.statement)).toBeVisible();

    const search = landscape.getByRole("textbox", { name: "Search outcomes" });
    await search.fill("deploy");
    await landscape.getByRole("button", { name: "Search" }).click();

    // The sidecar's answer, not a filtered copy: only the matching statement
    // stays, and the count beside it is the store's total.
    await expect(landscape.getByText(UNDERSERVED.statement)).toBeVisible();
    await expect(landscape.getByText(SERVED.statement)).toBeHidden();
    await expect(landscape.getByText("1 outcome matches these filters")).toBeVisible();

    await search.fill("elephants");
    await landscape.getByRole("button", { name: "Search" }).click();

    // An impossible filter is named as such, rather than falling back to the
    // whole library behind the person's back.
    await expect(landscape.getByText("Nothing matches these filters")).toBeVisible();

    await landscape.getByRole("button", { name: "Clear filters" }).click();
    await expect(landscape.getByText(SERVED.statement)).toBeVisible();
    await expect(landscape.getByText(/all 2 outcomes in the library/i)).toBeVisible();
  });

  test("a score band asks for the underserved outcomes", async ({ page, request }) => {
    await seedOutcomes(request, [UNDERSERVED, SERVED]);
    await openStudio(page);

    await rail(page).getByRole("button", { name: /^Landscape,/ }).click();
    const landscape = page.getByRole("complementary", { name: "Opportunity landscape" });
    await landscape.getByRole("button", { name: "📋 Table View" }).click();

    // 15.30 is underserved and 8.80 is not, so a band from 10 keeps one row.
    await landscape.getByRole("spinbutton", { name: "Minimum score" }).fill("10");
    await landscape.getByRole("button", { name: "Search" }).click();

    await expect(landscape.getByText(UNDERSERVED.statement)).toBeVisible();
    await expect(landscape.getByText(SERVED.statement)).toBeHidden();
    await expect(landscape.getByRole("button", { name: "Remove score filter" })).toBeVisible();
  });

  test("switches between the matrix, card, and table views", async ({ page, request }) => {
    await seedOutcomes(request, [UNDERSERVED, SERVED]);
    await openStudio(page);

    await rail(page).getByRole("button", { name: /^Landscape,/ }).click();
    const landscape = page.getByRole("complementary", { name: "Opportunity landscape" });

    await expect(landscape.getByRole("button", { name: "📊 Matrix" })).toBeVisible();

    await landscape.getByRole("button", { name: "🎴 Visual Cards" }).click();
    await expect(landscape.getByRole("button", { name: "🎴 Visual Cards" })).toBeVisible();

    await landscape.getByRole("button", { name: "📋 Table View" }).click();
    await expect(landscape.getByRole("columnheader", { name: "Opp. Score" })).toBeVisible();
  });
});
