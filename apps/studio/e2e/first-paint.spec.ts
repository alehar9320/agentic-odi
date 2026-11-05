import { expect, test, type Page } from "@playwright/test";

import { openStudio } from "./helpers";

/**
 * The shell that paints before JavaScript runs.
 *
 * A cold load must never be the browser's white canvas, and it must be the
 * right colour the first time. These tests cut the module bundle off at the
 * network so only the document — its inline style and its inline theme script —
 * can paint, then read what the browser actually resolved.
 *
 * The shell is a fixed, full-viewport layer, so its resolved background is the
 * first paint. The colours are the `--bg` token in `src/styles/tokens.css`,
 * which `bootShell.test.ts` keeps the inline copies in step with.
 */

const DARK_BG = "rgb(10, 11, 14)"; // #0a0b0e
const LIGHT_BG = "rgb(245, 246, 248)"; // #f5f6f8

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
    // Cut the module bundle off: nothing but the document can have run.
    await page.route("**/*.js", (route) => route.abort());
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
    await page.route("**/*.js", (route) => route.abort());
    await page.emulateMedia({ colorScheme: "light" });
    await page.goto("/");

    await expect(page.locator("html")).toHaveClass(/theme-dark/);
    expect(await shellBackground(page)).toBe(DARK_BG);
  });

  test("nothing stored follows the system, without the bundle", async ({ page }) => {
    await page.route("**/*.js", (route) => route.abort());
    await page.emulateMedia({ colorScheme: "light" });
    await page.goto("/");

    await expect(page.locator("html")).toHaveClass(/theme-light/);
    expect(await shellBackground(page)).toBe(LIGHT_BG);
  });

  test("a stored system choice is the system's answer, without the bundle", async ({ page }) => {
    // ALH-201 makes `system` a choice the Settings control writes, so the
    // pre-paint script must read it as deference to the operating system rather
    // than as an unknown value to fall back from.
    await page.addInitScript(() => {
      window.localStorage.setItem("studio.settings", JSON.stringify({ theme: "system" }));
    });
    await page.route("**/*.js", (route) => route.abort());
    await page.emulateMedia({ colorScheme: "light" });
    await page.goto("/");

    await expect(page.locator("html")).toHaveClass(/theme-light/);
    expect(await shellBackground(page)).toBe(LIGHT_BG);
  });
});

test.describe("a system choice tracks the operating system", () => {
  test("follows a palette the operating system changes to while the studio is open", async ({
    page,
  }) => {
    await page.addInitScript(() => {
      window.localStorage.setItem("studio.settings", JSON.stringify({ theme: "system" }));
    });
    await page.emulateMedia({ colorScheme: "dark" });
    await page.goto("/");
    await expect(page.locator("html")).toHaveClass(/theme-dark/);

    // Sunset, or a person who had the change queued: nothing is reloaded here.
    await page.emulateMedia({ colorScheme: "light" });
    await expect(page.locator("html")).toHaveClass(/theme-light/);
    const body = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
    expect(body).toBe(LIGHT_BG);
  });

  test("a pinned palette stays pinned when the operating system changes", async ({ page }) => {
    await page.addInitScript(() => {
      window.localStorage.setItem("studio.settings", JSON.stringify({ theme: "light" }));
    });
    await page.emulateMedia({ colorScheme: "light" });
    await page.goto("/");
    await expect(page.locator("html")).toHaveClass(/theme-light/);

    await page.emulateMedia({ colorScheme: "dark" });
    await expect(page.locator("html")).toHaveClass(/theme-light/);
    const body = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
    expect(body).toBe(LIGHT_BG);
  });

  test("choosing System in Settings hands the palette back to the operating system", async ({
    page,
  }) => {
    await page.addInitScript(() => {
      window.localStorage.setItem("studio.settings", JSON.stringify({ theme: "dark" }));
    });
    await page.emulateMedia({ colorScheme: "light" });
    await openStudio(page);
    // A pinned choice outranks the system on the way in.
    await expect(page.locator("html")).toHaveClass(/theme-dark/);

    await page.getByRole("button", { name: "Open settings" }).click();
    await page
      .getByRole("radiogroup", { name: "Theme" })
      .getByRole("radio", { name: "System" })
      .check();

    await expect(page.locator("html")).toHaveClass(/theme-light/);
    const stored = await page.evaluate(
      () => JSON.parse(window.localStorage.getItem("studio.settings") || "{}").theme,
    );
    expect(stored).toBe("system");
  });

  test("the theme control answers the keyboard and shows which option it is on", async ({
    page,
  }) => {
    await page.addInitScript(() => {
      window.localStorage.setItem("studio.settings", JSON.stringify({ theme: "light" }));
    });
    await openStudio(page);
    await page.getByRole("button", { name: "Open settings" }).click();

    const group = page.getByRole("radiogroup", { name: "Theme" });
    // The group is a native radio group, so the arrows are its own keyboard
    // contract: entry at the checked option, `Right` for the next palette.
    await group.getByRole("radio", { name: "Light" }).focus();
    await page.keyboard.press("ArrowRight");
    const dark = group.getByRole("radio", { name: "Dark" });
    await expect(dark).toBeChecked();
    const stored = await page.evaluate(
      () => JSON.parse(window.localStorage.getItem("studio.settings") || "{}").theme,
    );
    expect(stored).toBe("dark");

    // And the ring is on the pill the person looks at, not only on the input
    // inside it, so keyboard focus is visible where the choice is. Its colour
    // is the accent of the palette that choice just applied — #8b8cf8, dark —
    // which is the point: the ring follows the theme rather than a fixed grey.
    const focusedPill = group.locator(".theme-choice:has(:focus-visible)");
    await expect(focusedPill).toHaveCount(1);
    await expect(focusedPill).toHaveCSS("outline-width", "2px");
    await expect(focusedPill).toHaveCSS("outline-color", "rgb(139, 140, 248)");
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
