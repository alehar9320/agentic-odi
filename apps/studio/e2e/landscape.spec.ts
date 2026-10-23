import { expect, test } from "@playwright/test";

import { openStudio, rail, resetRepository, seedOutcomes } from "./helpers";

/**
 * The Opportunity Landscape is where scored outcomes are read. These tests
 * cover the parts a user relies on: the headline numbers, the score pills on
 * each card, and the filter that narrows the view to what is underserved.
 */

const UNDERSERVED = {
  statement: "Minimize the time to deploy a service",
  importance: 9.2,
  satisfaction: 3.1,
};
const SERVED = {
  statement: "Minimize the effort to rotate expired tokens",
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

  test("filters to underserved outcomes only", async ({ page, request }) => {
    await seedOutcomes(request, [UNDERSERVED, SERVED]);
    await openStudio(page);

    await rail(page).getByRole("button", { name: /^Landscape,/ }).click();
    const landscape = page.getByRole("complementary", { name: "Opportunity landscape" });

    // The table view lists each outcome by statement.
    await landscape.getByRole("button", { name: "📋 Table View" }).click();
    await expect(landscape.getByText(UNDERSERVED.statement)).toBeVisible();
    await expect(landscape.getByText(SERVED.statement)).toBeVisible();

    await landscape.getByLabel("Show Underserved Only (>10)").check();

    await expect(landscape.getByText(UNDERSERVED.statement)).toBeVisible();
    await expect(landscape.getByText(SERVED.statement)).toBeHidden();
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
