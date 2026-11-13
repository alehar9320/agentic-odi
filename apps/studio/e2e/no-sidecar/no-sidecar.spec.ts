import { expect, test, type Page } from "@playwright/test";

import { COMPOSER, CONVERSATION, openStudio, sendMessage } from "../helpers";

/**
 * #347: the state the product is most often in is the one the sidecar-backed
 * suite never tests. Every request under `/api` here answers 503 with an HTML
 * body, which is what a dead reverse proxy (or a hosted Worker with no sidecar)
 * returns, so the client's transport check is exercised rather than bypassed.
 */
const JOB = "Get a service from commit to production";
const STATEMENT = "Minimize the time it takes to rotate deployment secrets";
/** What `writeReceipt` says when a write landed in the browser store. */
const PENDING_RECEIPT = "Saved on this device · will sync";

/**
 * Page errors are collected per test. A caught fetch failure is not a
 * `pageerror`; an uncaught exception during boot or a turn is, and the promise
 * under test is that neither happens.
 */
let pageErrors: string[] = [];

test.beforeEach(async ({ page }) => {
  pageErrors = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));
  await page.route("**/api/**", (route) =>
    route.fulfill({
      status: 503,
      contentType: "text/html",
      body: "Service Unavailable",
    }),
  );
});

test.afterEach(() => {
  expect(pageErrors).toEqual([]);
});

/** The statements in the browser store, read the way a person's own copy would be. */
async function storedStatements(page: Page): Promise<string[]> {
  return page.evaluate(async () => {
    const db = await new Promise<IDBDatabase>((resolve, reject) => {
      const request = indexedDB.open("agentic-odi-studio");
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
    try {
      return await new Promise<string[]>((resolve, reject) => {
        const transaction = db.transaction("outcomes", "readonly");
        const request = transaction.objectStore("outcomes").getAll();
        request.onsuccess = () =>
          resolve(
            (request.result as { statement?: string }[]).map((row) => row.statement ?? ""),
          );
        request.onerror = () => reject(request.error);
      });
    } finally {
      db.close();
    }
  });
}

test("runs with no sidecar process on 8100", async ({ request }) => {
  // The acceptance contract is a harness, not a demo: if a developer leaves the
  // sidecar running, the suite must fail rather than quietly test the old path.
  await expect(
    request.get("http://127.0.0.1:8100/health", { timeout: 1_000 }),
  ).rejects.toThrow();
});

test("loads the stage without a red wall", async ({ page }) => {
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

test("answers from the browser assistant", async ({ page }) => {
  await openStudio(page);
  await sendMessage(page, "What is the weather tomorrow?");

  const log = page.getByRole("log", { name: CONVERSATION });
  await expect(log).toContainText("Local draft, no model connected");
  await expect(log).toContainText("Your canvas has 0 jobs");
  await expect(log).toContainText("add outcome");
});

test("captures a job and an outcome, then keeps them across a reload", async ({ page }) => {
  await openStudio(page);

  // The rail is derived from the canvas, so a first run has none. The Job Map
  // is reachable by command, and its empty state is the by-hand door.
  const composer = page.getByRole("textbox", { name: COMPOSER });
  await composer.fill("/");
  const palette = page.getByRole("listbox", { name: /commands/i });
  await expect(palette).toBeVisible();
  await palette.getByRole("option", { name: /^\/jobmap/ }).click();
  await page.getByRole("button", { name: "Capture what you know" }).click();
  await expect(page.getByLabel("Job name")).toBeVisible();

  await page.getByLabel("Job name").fill(JOB);
  await page.getByRole("button", { name: "Add job" }).click();
  // A browser-only write is acknowledged as a local save, not as a sidecar ack.
  await expect(page.getByText(PENDING_RECEIPT).first()).toBeVisible();

  await page.getByLabel("Desired outcome").fill(STATEMENT);
  await page.getByRole("button", { name: "Record outcome" }).click();
  // Both writes were acknowledged as local saves; the browser store is where
  // the outcome actually is, so wait on that rather than on a sidecar receipt.
  await expect.poll(async () => await storedStatements(page)).toContain(STATEMENT);
  await expect(page.locator(".banner").filter({ hasText: "That write was rejected" })).toHaveCount(
    0,
  );

  await page.reload();
  await expect(page.getByRole("textbox", { name: COMPOSER })).toBeVisible();

  const rail = page.getByRole("navigation", { name: "Your work" });
  await expect(rail).toBeVisible();
  await rail.getByRole("button", { name: /Landscape/ }).click();
  await expect(page.getByText(STATEMENT).first()).toBeVisible();
});
