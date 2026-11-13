import { expect, test } from "@playwright/test";

import { offlineNotice, openStudio } from "./helpers";

/**
 * The motion budget, proven in a browser (issue #336).
 *
 * `src/styles/motion.test.ts` reads the stylesheet and catches a new inline
 * duration at review time. It cannot see what the page actually computes: a
 * `var()` that resolves to nothing, or a loop that keeps running under the
 * preference. This spec reads `getComputedStyle` on real elements with reduced
 * motion emulated, which is the claim the budget makes.
 */
test.describe("motion budget", () => {
  test("reduced motion collapses transitions and leaves nothing looping", async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await openStudio(page);

    // A banner is the studio's most animated surface — it enters and, before
    // this change, its downloading mark throbbed forever.
    const banner = offlineNotice(page);
    await expect(banner).toBeVisible();

    const bannerMotion = await banner.evaluate((node) => {
      const style = getComputedStyle(node);
      return {
        transition: style.transitionDuration,
        animation: style.animationDuration,
        iterations: style.animationIterationCount,
      };
    });
    expect(bannerMotion.transition.split(",").every((d) => parseFloat(d) < 0.01)).toBe(true);

    // Nothing anywhere on the page may keep animating under the preference.
    const running = await page.evaluate(() =>
      Array.from(document.querySelectorAll("*"))
        .map((node) => getComputedStyle(node))
        .filter(
          (style) =>
            style.animationName !== "none" &&
            style.animationIterationCount !== "1" &&
            parseFloat(style.animationDuration) > 0,
        )
        .map((style) => style.animationName),
    );
    expect(running).toEqual([]);
  });

  test("a banner entrance is near-instant under reduced motion and animated otherwise", async ({
    page,
  }) => {
    await page.emulateMedia({ reducedMotion: "no-preference" });
    await openStudio(page);

    const banner = offlineNotice(page);
    await expect(banner).toBeVisible();
    const animated = await banner.evaluate(
      (node) => parseFloat(getComputedStyle(node).animationDuration) > 0,
    );
    expect(animated).toBe(true);
  });
});
