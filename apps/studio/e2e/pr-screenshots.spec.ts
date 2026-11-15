import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

import { COMPOSER, lens, openStudio, rail, resetRepository, seedOutcomes } from "./helpers";

/**
 * Product screenshots for human review, not for assertions.
 *
 * This spec drives the real Studio against the real sidecar and writes one PNG
 * per key screen into `apps/studio/pr-screenshots/`. The `pr-screenshots`
 * workflow posts them as a comment on the pull request so a reviewer sees the
 * running product without cloning or building. Nothing here asserts on the
 * pixels: a failure is reported and the remaining screens are still captured,
 * because the point is to show a person what the product looks like.
 *
 * It is deliberately outside the `test:e2e` project (see `playwright.config.ts`)
 * so the end-to-end job keeps exactly the coverage it has today.
 */

const OUT_DIR = "pr-screenshots";

// Three scored outcomes give the landscape and the records table real rows.
// Statements carry an execution context and a unit of measure, which the
// repository's ODI format check requires before it will store an outcome.
const OUTCOMES = [
  {
    statement: "Minimize the time it takes to deploy a service when releasing a hotfix",
    importance: 9.2,
    satisfaction: 3.1,
  },
  {
    statement: "Minimize the number of manual checks needed to prove a deploy is safe when a reviewer is away",
    importance: 8.4,
    satisfaction: 5.0,
  },
  {
    statement: "Minimize the time to detect a partial rollout when a canary looks healthy early",
    importance: 7.6,
    satisfaction: 6.2,
  },
];

/** Put a few job-map steps behind the job the outcomes were seeded against. */
async function seedJobMap(request: APIRequestContext): Promise<void> {
  const canvas = (await (await request.get("/api/canvas")).json()) as {
    jobs: { id: string }[];
  };
  const jobId = canvas.jobs[0]?.id;
  expect(jobId).toBeTruthy();

  const steps = [
    "Locate the service to release",
    "Prepare the change and its rollback",
    "Release the change to production",
  ];
  for (const [index, name] of steps.entries()) {
    const created = await request.post("/api/steps", {
      data: { mcp_url: "", job_id: jobId, name, order: index + 1 },
    });
    expect(created.ok()).toBeTruthy();
  }
}

/** Write one full-page PNG, reporting a failure instead of aborting the run. */
async function capture(page: Page, name: string): Promise<void> {
  try {
    await page.waitForFunction(() => document.fonts.status === "loaded");
    await page.screenshot({ path: `${OUT_DIR}/${name}`, fullPage: true });
    test.info().annotations.push({ type: "screenshot", description: name });
  } catch (error) {
    test.info().annotations.push({
      type: "screenshot-failed",
      description: `${name}: ${String(error)}`,
    });
  }
}

/** Close the open lens so the next screen starts from the stage. */
async function closeLens(page: Page): Promise<void> {
  const close = page.getByRole("button", { name: "Close workspace view" }).first();
  if (await close.isVisible().catch(() => false)) {
    await close.click();
    await expect(lens(page)).toBeHidden();
  }
}

/** Open a lens through the workbench rail. */
async function openFromRail(page: Page, name: RegExp): Promise<void> {
  await rail(page).getByRole("button", { name }).click();
  await expect(lens(page)).toBeVisible();
}

/** Open a lens through its slash command, which works without rail content. */
async function openFromCommand(page: Page, command: string): Promise<void> {
  await page.getByRole("textbox", { name: COMPOSER }).fill(command);
  await page.keyboard.press("Enter");
  await expect(lens(page)).toBeVisible();
}

test.describe("product screenshots", () => {
  test.beforeEach(async ({ request }) => {
    await resetRepository(request);
  });

  test("captures the key screens", async ({ page, request }) => {
    await seedOutcomes(request, OUTCOMES);
    await seedJobMap(request);

    // 01 — the first screen the Studio paints, with the rail already holding
    // what the thread has produced.
    await openStudio(page);
    await capture(page, "01-home.png");

    // 02 — the transcript after one message has rendered.
    await page.getByRole("textbox", { name: COMPOSER }).fill("Walk me through the job map.");
    await page.getByRole("button", { name: "Send message" }).click();
    const reply = page.getByRole("log", { name: "Conversation" }).locator(".message--assistant");
    await expect(reply.last().getByRole("button", { name: "Copy reply" })).toBeVisible();
    await capture(page, "02-chat.png");

    // 03 — the job map, opened from the rail.
    await openFromRail(page, /^Job map,/);
    await capture(page, "03-job-map.png");
    await closeLens(page);

    // 04 — the opportunity landscape, opened from the rail.
    await openFromRail(page, /^Landscape,/);
    await capture(page, "04-landscape.png");
    await closeLens(page);

    // 05 — the segments lens. Segments are derived by `segment_market`, which
    // no route exposes, so this is opened by command and shows whatever the
    // store honestly holds.
    await openFromCommand(page, "/segments");
    await capture(page, "05-segments.png");
    await closeLens(page);

    // 06 — the decision brief, opened by command like `brief.spec.ts` does.
    await openFromCommand(page, "/brief");
    await capture(page, "06-brief.png");
  });
});
