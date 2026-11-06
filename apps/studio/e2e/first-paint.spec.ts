import { expect, test, type Page } from "@playwright/test";

/**
 * The shell that paints before JavaScript runs.
 *
 * A cold load must never be the browser's white canvas, and it must be the
 * right colour the first time. These tests cut the module bundle off at the
 * network so only the document and its own bootstrap files can paint —
 * `boot.css` for the colours and `boot-theme.js` for the theme class — then
 * read what the browser actually resolved.
 *
 * The shell is a fixed, full-viewport layer, so its resolved background is the
 * first paint. The colours are the `--bg` token in `src/styles/theme.css`,
 * which `bootShell.test.ts` keeps the inline copies in step with.
 */

const DARK_BG = "rgb(10, 11, 14)"; // #0a0b0e
const LIGHT_BG = "rgb(245, 246, 248)"; // #f5f6f8

/**
 * The React bundle: Vite's hashed entry under `/assets`, and nothing else.
 *
 * Aborting it leaves the document and its own bootstraps running while React
 * never mounts, which is the frame these tests measure. The bootstraps are
 * separate same-origin files (the strict CSP refuses inline script and style),
 * so they are deliberately not part of this pattern.
 */
const REACT_BUNDLE = "**/assets/*.js";

/** The colour the window shows first: the covering shell layer. */
async function shellBackground(page: Page): Promise<string> {
  return page
    .locator("#boot")
    .evaluate((node) => getComputedStyle(node).backgroundColor);
}

test.describe("the shell paints before JavaScript", () => {
  test("with JavaScript off, the shell and its spine are in the document", async ({ browser }) => {
    const context = await browser.newContext({ javaScriptEnabled: false, colorScheme: "dark" });
    const page = await context.newPage();
    await page.goto("/");

    // The shell is in the document, so it is there even when nothing runs.
    await expect(page.locator("#boot")).toBeVisible();
    await expect(page.locator(".boot-shell__bar")).toBeVisible();
    await expect(page.locator(".boot-shell__rail")).toBeVisible();
    await expect(page.locator(".boot-shell__stage")).toBeVisible();

    expect(await shellBackground(page)).toBe(DARK_BG);
    await context.close();
  });

  test("with JavaScript off and a light system, the shell is the light token", async ({ browser }) => {
    const context = await browser.newContext({
      javaScriptEnabled: false,
      colorScheme: "light",
    });
    const page = await context.newPage();
    await page.goto("/");

    await expect(page.locator("#boot")).toBeVisible();
    // The media query decides when no script has resolved a class.
    expect(await shellBackground(page)).toBe(LIGHT_BG);
    await context.close();
  });

  test("with JavaScript off and a dark system, the shell is the dark token", async ({ browser }) => {
    const context = await browser.newContext({
      javaScriptEnabled: false,
      colorScheme: "dark",
    });
    const page = await context.newPage();
    await page.goto("/");

    expect(await shellBackground(page)).toBe(DARK_BG);
    await context.close();
  });
});

test.describe("the theme is resolved before React", () => {
  test("a stored light theme wins over a dark system, without the bundle", async ({ page }) => {
    await page.addInitScript(() => {
      window.localStorage.setItem("studio.settings", JSON.stringify({ theme: "light" }));
    });
    // Cut the React bundle off: nothing but the document and its bootstraps ran.
    await page.route(REACT_BUNDLE, (route) => route.abort());
    await page.emulateMedia({ colorScheme: "dark" });
    await page.goto("/");

    await expect(page.locator("html")).toHaveClass(/theme-light/);
    await expect(page.locator("html")).not.toHaveClass(/theme-dark/);
    expect(await shellBackground(page)).toBe(LIGHT_BG);
  });

  test("a stored dark theme wins over a light system, without the bundle", async ({ page }) => {
    await page.addInitScript(() => {
      window.localStorage.setItem("studio.settings", JSON.stringify({ theme: "dark" }));
    });
    await page.route(REACT_BUNDLE, (route) => route.abort());
    await page.emulateMedia({ colorScheme: "light" });
    await page.goto("/");

    await expect(page.locator("html")).toHaveClass(/theme-dark/);
    expect(await shellBackground(page)).toBe(DARK_BG);
  });

  test("nothing stored follows the system, without the bundle", async ({ page }) => {
    await page.route(REACT_BUNDLE, (route) => route.abort());
    await page.emulateMedia({ colorScheme: "light" });
    await page.goto("/");

    await expect(page.locator("html")).toHaveClass(/theme-light/);
    expect(await shellBackground(page)).toBe(LIGHT_BG);
  });
});

test.describe("the handover", () => {
  test("React removes the shell and keeps the same colour", async ({ page }) => {
    await page.addInitScript(() => {
      window.localStorage.setItem("studio.settings", JSON.stringify({ theme: "dark" }));
    });
    await page.emulateMedia({ colorScheme: "dark" });
    await page.goto("/");

    // The app is mounted (its bundle was not blocked here) and the shell is gone.
    await expect(page.locator("#boot")).toHaveCount(0);
    await expect(page.getByRole("textbox", { name: "Message the studio" })).toBeVisible();

    // The class the inline script painted is the class the app keeps, and the
    // page background is the same token the shell showed: one colour across the
    // handover, not a dark-to-light flash.
    await expect(page.locator("html")).toHaveClass(/theme-dark/);
    const body = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
    expect(body).toBe(DARK_BG);
  });

  test("a light-theme user keeps the light shell across the handover", async ({ page }) => {
    await page.addInitScript(() => {
      window.localStorage.setItem("studio.settings", JSON.stringify({ theme: "light" }));
    });
    await page.emulateMedia({ colorScheme: "dark" });
    await page.goto("/");

    await expect(page.locator("#boot")).toHaveCount(0);
    await expect(page.getByRole("textbox", { name: "Message the studio" })).toBeVisible();

    // The bootstrap resolved light before React; React must not flip it to dark.
    await expect(page.locator("html")).toHaveClass(/theme-light/);
    const body = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
    expect(body).toBe(LIGHT_BG);
  });
});
