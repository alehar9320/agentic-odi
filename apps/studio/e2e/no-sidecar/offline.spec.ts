import { expect, test } from "@playwright/test";

/**
 * #546: a deep link opened while offline, whose shell was never cached, must
 * land on the themed `/offline.html` rather than the browser's error page.
 *
 * This is the one test that exercises the real service worker in a real
 * browser: the worker registers, precaches the page, and then a navigation is
 * cut off at the network so the fallback is the only thing left.
 */
test.describe("the offline fallback", () => {
  /**
   * Load the Studio and wait until the service worker controls this page.
   *
   * A freshly registered worker does not control the page that registered it
   * until it activates and claims clients, so the reload makes control certain
   * before the network is cut.
   */
  async function openStudioWithWorker(page: import("@playwright/test").Page) {
    await page.goto("/?flags=firstRunWizard:off");
    await page.waitForFunction(async () => {
      const registration = await navigator.serviceWorker.getRegistration();
      return Boolean(registration?.active);
    });
    await page.reload();
    await page.waitForFunction(() => Boolean(navigator.serviceWorker.controller));
  }

  test("serves the offline page for an uncached navigation with no network", async ({
    page,
    context,
  }) => {
    await openStudioWithWorker(page);

    await context.setOffline(true);
    // A deep link whose shell was never fetched this session: the navigation
    // cannot be answered from the network or from the shell cache.
    const response = await page.goto("/records/never-visited-while-online");

    expect(response?.status()).toBe(200);
    await expect(
      page.getByRole("heading", { name: /offline, and this page was not saved/i }),
    ).toBeVisible();
    await expect(page.getByRole("link", { name: "Open the Studio" })).toHaveAttribute(
      "href",
      "/",
    );
    await expect(page.getByText(/Still yours, on this device/)).toBeVisible();
  });

  test("opens the offline page in the stored theme", async ({ page, context }) => {
    await page.addInitScript(() => {
      window.localStorage.setItem(
        "studio.settings",
        JSON.stringify({ theme: "light" }),
      );
    });
    await openStudioWithWorker(page);

    await context.setOffline(true);
    await page.goto("/records/never-visited-while-online");

    // The page reads `studio.settings` before paint and marks the palette on
    // the root element, so the stored light theme is the one that renders.
    await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
    await expect
      .poll(() => page.evaluate(() => getComputedStyle(document.body).backgroundColor))
      .toBe("rgb(245, 246, 248)");
  });
});

/**
 * #546, task two: the in-app sentence. It is one line when the connection goes,
 * and acting while offline must not stack a copy of it.
 */
test.describe("the in-app offline sentence", () => {
  function offlineStrip(page: import("@playwright/test").Page) {
    return page.locator(".banner").filter({ hasText: "You're offline" });
  }

  test("says what still works once, and keeps it to one line through an action", async ({
    page,
    context,
  }) => {
    await page.goto("/?flags=firstRunWizard:off");
    await expect(page.getByRole("textbox", { name: "Message the studio" })).toBeVisible();
    // A fresh studio offers a connector in a modal; it is real product behavior,
    // so dismiss it the way a user would before acting.
    const suggestion = page.getByRole("dialog", { name: "Connector suggestion" });
    await suggestion.waitFor({ state: "visible", timeout: 2_000 }).catch(() => {});
    if (await suggestion.isVisible()) {
      await suggestion.getByRole("button", { name: "Not now" }).click();
      await expect(suggestion).toBeHidden();
    }

    await context.setOffline(true);
    await expect(offlineStrip(page)).toBeVisible();
    await expect(offlineStrip(page)).toHaveCount(1);
    await expect(offlineStrip(page)).toContainText(/on this device/i);

    // Acting while offline must not add a second copy of the same sentence.
    const composer = page.getByRole("textbox", { name: "Message the studio" });
    await composer.fill("Where do I start?");
    await page.getByRole("button", { name: "Send message" }).click();
    await expect(
      page.getByRole("log", { name: "Conversation" }).getByText("Where do I start?"),
    ).toBeVisible();

    await expect(offlineStrip(page)).toHaveCount(1);
  });
});
