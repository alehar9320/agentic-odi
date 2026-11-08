import { expect, test } from "@playwright/test";

/**
 * #545: the built app opens with no network.
 *
 * This is the one spec that exercises the real service worker in a real browser.
 * The worker registers, precaches the built shell, and then the network is cut so
 * the cache is the only thing left. It also proves the two guardrails: no API
 * response is ever served from cache, and an update never activates on its own.
 */

/** The origin-root path of the app's shell document. */
const SHELL = "/index.html";

/** The app URL with the first-run wizard off, so the shell is what renders. */
const APP = "/?flags=firstRunWizard:off";

/**
 * Load the Studio and wait until the service worker controls this page and has
 * precached the shell.
 *
 * A freshly registered worker does not control the page that registered it until
 * it activates and claims clients, so the reload makes control certain before the
 * network is cut. The cache wait makes the precache certain too — a navigation
 * that lands before the install finished would be answered by the network, not
 * the shell.
 */
async function openStudioWithWorker(page: import("@playwright/test").Page) {
  await page.goto(APP);
  await page.waitForFunction(async () => {
    const registration = await navigator.serviceWorker.getRegistration();
    return Boolean(registration?.active);
  });
  await page.reload();
  await page.waitForFunction(() => Boolean(navigator.serviceWorker.controller));
  // The update listener attaches on `load`; wait for it so a test that stages a
  // new build cannot fire `updatefound` before the page is listening.
  await page.waitForLoadState("load");
  await page.waitForFunction(async (shell) => {
    const names = await caches.keys();
    const name = names.find((entry) => entry.startsWith("studio-shell-"));
    if (!name) {
      return false;
    }
    const cache = await caches.open(name);
    return Boolean(await cache.match(shell));
  }, SHELL);
}

test.describe("the shell opens with no network", () => {
  test("renders the app from cache when a reload has no network", async ({ page, context }) => {
    await openStudioWithWorker(page);

    await context.setOffline(true);
    // A reload with no network: the shell comes from the cache and the app boots,
    // reading its canvas from IndexedDB rather than a network error page.
    const response = await page.goto(APP);

    expect(response?.status()).toBe(200);
    await expect(page.getByRole("textbox", { name: "Message the studio" })).toBeVisible();
    // The banner renders its title and an aria-live announcement, so match the
    // visible title rather than the text, which would be two elements.
    await expect(page.locator(".banner__title", { hasText: /you're offline/i })).toBeVisible();
  });

  test("serves the offline page only when the shell cache was evicted", async ({ page, context }) => {
    await openStudioWithWorker(page);

    // Evict the shell from the cache the way storage pressure would, leaving the
    // offline page. The fallback is then the only thing that can answer.
    await page.evaluate(async (shell) => {
      const names = await caches.keys();
      const name = names.find((entry) => entry.startsWith("studio-shell-"));
      const cache = name ? await caches.open(name) : null;
      await cache?.delete(shell);
    }, SHELL);

    await context.setOffline(true);
    const response = await page.goto("/records/never-visited-while-online");

    expect(response?.status()).toBe(200);
    await expect(
      page.getByRole("heading", { name: /offline, and this page was not saved/i }),
    ).toBeVisible();
    await expect(page.getByRole("link", { name: "Open the Studio" })).toHaveAttribute("href", "/");
    await expect(page.getByText(/Still yours, on this device/)).toBeVisible();
  });
});

/**
 * #545, task two: never cache the API. A cached canvas response would defeat the
 * BFF's fallback and the conflict rules, and an offline call must fail fast.
 */
test.describe("the API is never served from cache", () => {
  test("reads the network online and fails fast offline", async ({ page, context }) => {
    await openStudioWithWorker(page);

    // Warm whatever cache the worker owns with a real read.
    const online = await page.evaluate(async () => {
      const response = await fetch("/api/canvas");
      return response.status;
    });
    expect(online).toBe(200);

    await context.setOffline(true);
    const offline = await page.evaluate(async () => {
      const started = Date.now();
      try {
        const response = await fetch("/api/canvas");
        return { reached: true, status: response.status, ms: Date.now() - started };
      } catch {
        return { reached: false, ms: Date.now() - started };
      }
    });

    // The cached response is not served: the request reaches the network and
    // fails. It fails quickly, rather than hanging on a cache lookup.
    expect(offline.reached).toBe(false);
    expect(offline.ms).toBeLessThan(2_000);
  });
});

/**
 * #545, task three: update without a trap. A new build waits until the person
 * asks, so activating it can never reload the page under a streamed turn.
 */
test.describe("a new build waits for a person", () => {
  test("offers one reload when a new worker is waiting, and never reloads on its own", async ({
    page,
    context,
  }) => {
    // A version marker makes a later fetch of the worker byte-different, which is
    // what makes the browser install it as an update.
    let version = "v1";
    await context.route("**/sw.js", async (route) => {
      const response = await route.fetch();
      const body = await response.text();
      await route.fulfill({ response, body: `${body}\n// ${version}\n` });
    });

    await openStudioWithWorker(page);

    // A new build is published and the browser checks for it.
    version = "v2";
    await page.evaluate(async () => {
      const registration = await navigator.serviceWorker.getRegistration();
      await registration?.update();
    });

    const offer = page.locator(".banner__title", { hasText: /a new version of the studio is ready/i });
    await expect(offer).toBeVisible();
    // One offer, never a loop.
    await expect(offer).toHaveCount(1);

    // The page did not reload on its own: the offer is still the old document.
    await expect(page.getByRole("button", { name: "Reload for the new version" })).toBeVisible();
  });
});
