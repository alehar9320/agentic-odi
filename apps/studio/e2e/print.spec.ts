import { expect, test, type Page } from "@playwright/test";

import { openStudio, rail, resetRepository, seedOutcomes, setTheme } from "./helpers";

/**
 * Paper (ALH-216).
 *
 * `src/styles/print.test.ts` reads the print sheet and can say a rule exists;
 * it cannot say the rule wins. Because `theme.css` imports the sheet on its
 * first line, every screen rule arrives later in the cascade, so a print value
 * of the same specificity is a dead letter and the sheet prints the dark plot
 * ground it was supposed to replace. This is the pass that measures what the
 * browser paints under print media, in the theme a person is least likely to
 * think about before hitting Ctrl-P.
 *
 * The bands are asserted by shape as well as by grey: on a greyscale sheet the
 * geometry is the whole claim that a deep gap is not a served one.
 */

test.use({ reducedMotion: "reduce" });

/** One outcome per band, by `importance + max(importance - satisfaction, 0)`. */
const OUTCOMES = [
  {
    statement: "Minimize the time to find the right runbook while the pager is still ringing",
    importance: 5,
    satisfaction: 4,
  },
  {
    statement: "Minimize the number of checks a release passes before deploy on a Friday",
    importance: 8,
    satisfaction: 4,
  },
  {
    statement: "Minimize the time to roll a bad release back when the queue is already drained",
    importance: 9.2,
    satisfaction: 3.1,
  },
];

/**
 * Every colour the sheet owes, read from the painted page in one pass.
 *
 * A single read straight after `emulateMedia` returns the screen value: the
 * media switch invalidates style, and the engine recomputes on the next frame.
 * Returning the whole snapshot lets `expect.poll` re-read until the page has
 * settled, so the gate waits for the repaint instead of asserting a frame that
 * has not happened yet.
 */
const paper = (page: Page) =>
  page.evaluate(() => {
    const ink = (
      selector: string,
      property: "backgroundColor" | "color" | "fill" | "stroke",
    ) => {
      const node = document.querySelector(selector);
      if (!node) {
        throw new Error(`the map draws no ${selector}`);
      }
      return getComputedStyle(node)[property];
    };
    const markers = ["served", "underserved", "deep"].map((band) => {
      const node = document.querySelector(`.opportunity-matrix__node--${band}`);
      if (!node) {
        throw new Error(`the map draws no ${band} marker`);
      }
      const style = getComputedStyle(node);
      return {
        shape: node.tagName.toLowerCase(),
        fill: style.fill,
        stroke: style.stroke,
      };
    });
    return {
      cardGround: ink(".opportunity-matrix__panel", "backgroundColor"),
      axisInk: ink(".opportunity-matrix__axis", "fill"),
      legendInk: ink(".opportunity-matrix__legend", "color"),
      markers,
    };
  });

test("prints the map as ink, not as a black sheet", async ({ page, request }) => {
  await resetRepository(request);
  await seedOutcomes(request, OUTCOMES);
  await setTheme(page, "dark");
  await openStudio(page);
  await rail(page).getByRole("button", { name: /^Landscape,/ }).click();
  await expect(page.locator(".opportunity-matrix__panel")).toBeVisible();

  // The negative control, taken first: on screen the card is the dark plot
  // ground, so the white below can only have come from the print sheet.
  const screen = await paper(page);
  expect(screen.cardGround).toBe("rgb(11, 13, 19)");
  expect(screen.axisInk).toBe("rgb(162, 167, 179)");

  await page.emulateMedia({ media: "print" });

  await expect
    .poll(() => paper(page))
    .toEqual({
      // Ink on white, and the card's ground is the page, not the plot.
      cardGround: "rgb(255, 255, 255)",
      axisInk: "rgb(68, 68, 68)",
      legendInk: "rgb(68, 68, 68)",
      markers: [
        { shape: "circle", fill: "rgb(68, 68, 68)", stroke: "rgb(255, 255, 255)" },
        { shape: "rect", fill: "rgb(136, 136, 136)", stroke: "rgb(255, 255, 255)" },
        { shape: "polygon", fill: "rgb(17, 17, 17)", stroke: "rgb(255, 255, 255)" },
      ],
    });

  // Three shapes, and three greys a photocopier keeps apart even when the
  // shapes are too small to read.
  const printed = await paper(page);
  expect(printed.markers.map((marker) => marker.shape)).toEqual(["circle", "rect", "polygon"]);
  expect(new Set(printed.markers.map((marker) => marker.fill)).size).toBe(3);
});
