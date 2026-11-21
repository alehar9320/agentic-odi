import { expect, test, type Page } from "@playwright/test";

import {
  assistantReplies,
  banners,
  COMPOSER,
  openStudio,
  rail,
  sendMessage,
  waitForStudioReady,
} from "../helpers";

/**
 * #347: the state the product is most often in is the one the sidecar-backed
 * suite never tests.
 *
 * This spec runs under `playwright.no-sidecar.config.ts`, which serves the
 * built SPA from `vite preview` and starts no sidecar. Each test then answers
 * `/api/**` itself, with one of the shapes a dead backend produces — a 503
 * HTML page (a reverse proxy with nothing behind it), a 502 (the hosted
 * Worker reporting `sidecar_unavailable`), or a socket error (nothing
 * listening at all). All three are transport failures, so the browser BFF must
 * serve every read and every write instead of the app refusing to work.
 */

const JOB = "Get a service from commit to production";
const STATEMENT = "Minimize the time it takes to rotate deployment secrets";
/** What `writeReceipt` says when a write landed in the browser store. */
const PENDING_RECEIPT = "Saved on this device · will sync";
/** The browser store the BFF owns (`bff/store/migrations.ts`). */
const CANVAS_DB = "agentic-odi-studio";

/**
 * Page errors are collected per test. A caught fetch failure is not a
 * `pageerror`; an uncaught exception during boot or a turn is, and the promise
 * under test is that neither happens.
 */
let pageErrors: string[] = [];

test.beforeEach(async ({ page }) => {
  pageErrors = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));
});

test.afterEach(() => {
  expect(pageErrors).toEqual([]);
});

/** Answer every API call the way a backend that is not there would. */
async function deadApi(page: Page, status: 502 | 503): Promise<void> {
  await page.route("**/api/**", (route) =>
    route.fulfill({
      status,
      contentType: "text/html",
      body: "Service Unavailable",
    }),
  );
}

/** Answer every API call the way a closed port would. */
async function unreachableApi(page: Page): Promise<void> {
  await page.route("**/api/**", (route) => route.abort("connectionrefused"));
}

/** The named field of every row in one browser-store table. */
async function stored(
  page: Page,
  store: "jobs" | "outcomes",
  field: "name" | "statement",
): Promise<string[]> {
  return page.evaluate(
    async ({ dbName, storeName, fieldName }) => {
      const db = await new Promise<IDBDatabase>((resolve, reject) => {
        const request = indexedDB.open(dbName);
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
      });
      try {
        return await new Promise<string[]>((resolve, reject) => {
          const transaction = db.transaction(storeName, "readonly");
          const request = transaction.objectStore(storeName).getAll();
          request.onsuccess = () =>
            resolve(
              (request.result as Record<string, unknown>[]).map((row) =>
                String(row[fieldName] ?? ""),
              ),
            );
          request.onerror = () => reject(request.error);
        });
      } finally {
        db.close();
      }
    },
    { dbName: CANVAS_DB, storeName: store, fieldName: field },
  );
}

test("runs with no sidecar process on 8100", async ({ request }) => {
  // The acceptance contract is a harness, not a demo: if a developer leaves the
  // sidecar running, the suite must fail rather than quietly test the old path.
  await expect(request.get("http://127.0.0.1:8100/health", { timeout: 1_000 })).rejects.toThrow();
});

test("loads the stage without a red wall", async ({ page }) => {
  await deadApi(page, 503);
  await openStudio(page);

  await expect(page.getByRole("textbox", { name: COMPOSER })).toBeVisible();
  await expect(page.locator(".error-page")).toHaveCount(0);

  // The only red surface allowed is the one line about the missing sidecar.
  const critical = page.locator(".banner--critical");
  await expect.poll(() => critical.count()).toBeLessThanOrEqual(1);
  for (const text of await critical.allInnerTexts()) {
    expect(text.toLowerCase()).toContain("sidecar");
  }
});

test("answers from the built-in assistant", async ({ page }) => {
  await deadApi(page, 503);
  await openStudio(page);
  await sendMessage(page, "What is the weather tomorrow?");

  const reply = assistantReplies(page).last();
  // The tag is styled as a badge, so the rendered text is uppercased.
  await expect(reply).toContainText(/built-in assistant/i);
  // The built-in assistant answers about this canvas rather than inventing one.
  await expect(reply).toContainText("Your canvas has 0 jobs");
});

test("answers the hosted Worker's 502 the same way", async ({ page }) => {
  await deadApi(page, 502);
  await openStudio(page);

  await expect(page.getByRole("textbox", { name: COMPOSER })).toBeVisible();
  await expect(page.locator(".error-page")).toHaveCount(0);

  await sendMessage(page, "What is the weather tomorrow?");
  await expect(assistantReplies(page).last()).toContainText(/built-in assistant/i);
});

test("answers when nothing is listening at all", async ({ page }) => {
  await unreachableApi(page);
  await openStudio(page);

  await expect(page.getByRole("textbox", { name: COMPOSER })).toBeVisible();
  await sendMessage(page, "What is the weather tomorrow?");
  await expect(assistantReplies(page).last()).toContainText(/built-in assistant/i);
});

test("captures a job and an outcome, then keeps them across a reload", async ({ page }) => {
  await deadApi(page, 503);
  await openStudio(page);

  // The by-hand door is the Job Map's empty state: a first run has no rail to
  // click, and `/capture` is a prompt, not a view, so it would start a turn.
  const composer = page.getByRole("textbox", { name: COMPOSER });
  await composer.fill("/jobmap");
  const palette = page.getByRole("listbox", { name: /commands/i });
  await expect(palette).toBeVisible();
  await palette.getByRole("option", { name: /^\/jobmap/ }).click();
  await page.getByRole("button", { name: "Capture what you know" }).click();

  const panel = page.getByRole("complementary", { name: "Capture by hand" });
  await expect(panel).toBeVisible();

  // A job first: an outcome is always a metric for a job.
  await panel.getByLabel("Job name").fill(JOB);
  await panel.getByRole("button", { name: "Add job" }).click();
  // A browser-only write is acknowledged as a local save, not as a sidecar ack.
  await expect(page.getByText(PENDING_RECEIPT).first()).toBeVisible();

  await panel.getByLabel("Desired outcome").fill(STATEMENT);
  await panel.getByRole("button", { name: "Record outcome" }).click();
  // The browser store is where the write actually landed, so wait on it rather
  // than on a receipt a sidecar would have produced.
  await expect.poll(async () => await stored(page, "jobs", "name")).toContain(JOB);
  await expect.poll(async () => await stored(page, "outcomes", "statement")).toContain(STATEMENT);
  await expect(banners(page).filter({ hasText: "That write was rejected" })).toHaveCount(0);

  await page.reload();
  await waitForStudioReady(page);
  await expect(rail(page)).toBeVisible();

  await rail(page)
    .getByRole("button", { name: /^Landscape,/ })
    .click();
  const landscape = page.getByRole("complementary", { name: "Opportunity landscape" });
  await expect(landscape).toBeVisible();
  await expect(landscape).toContainText(STATEMENT);
});
