import { expect, type Page, test } from "@playwright/test";

import { COMPOSER, lens, offlineNotice, openStudio, resetRepository } from "./helpers";

/**
 * The receipt that names the store.
 *
 * A board kept in this browser is real work, and the studio says so: a capture
 * made while the board is the browser's closes with "Saved in this browser."
 * rather than a bare "saved". Two halves have to hold, and a test that checks
 * only the first proves nothing — the clause must appear when the browser is
 * keeping the work, and must not appear when a server is.
 *
 * The board-with-no-server case is produced by refusing the board's endpoints at
 * the network layer. That is not a mock of studio logic, it is the scenario:
 * `withLocal` in `src/api/studioApi.ts` hands a read to the browser store only
 * when `isTransportFailure` reads the failure as *absence* — a fetch that never
 * completed, or a 502/503/504 with no structured body. Everything else on the
 * page still talks to the real sidecar, so the app boots, answers, and has to
 * decide for itself where the board lives.
 *
 * One reach limit is worth naming, because it is why the browser-board test
 * finishes the context wizard instead of capturing a job: the job, step, and
 * outcome writes go to `/api/jobs` and friends with no local fallback at this
 * base, so on a board with no server they fail and no success receipt is raised
 * for them at all. #616 wraps those writes, and the three clauses it makes
 * reachable are unit-tested in `src/state/StudioContext.test.tsx`. The context
 * wizard's receipt is reachable today, and this file pins it from the browser.
 */

const JOB = "Get a service from commit to production";
// An ODI outcome statement has to name its context, or the sidecar refuses it.
const OUTCOME = "Minimize the time from merge to production when releasing a hotfix";
const STEP = "Roll back without a meeting";

/** The five answers the introduction asks for, in its own order. */
const CONTEXT_ANSWERS = [
  "I'm the platform lead; the team is four engineers and a designer.",
  "The engineer on call when a deploy lands badly",
  "Get a service from commit to production without hand-copying config",
  "A missed key costs a deploy day",
  "Nine onboarding calls, one angry ticket, and a Slack thread",
];

/** The browser store the local BFF writes to (`src/bff/store/indexedDbStore.ts`). */
const LOCAL_DB = "agentic-odi-studio";

/** The clause a visitor should read when the board is theirs alone — spelled as they read it. */
const KEPT_HERE = "Saved in this browser.";

/**
 * Read the receipt while it is on screen.
 *
 * A toast lives for six seconds and this suite performs several writes in a row,
 * so the text is taken at the moment it appears rather than re-queried later
 * against an element that has already left.
 */
async function receipt(page: Page, named: string): Promise<string> {
  const banner = page.locator(".banner").filter({ hasText: named });
  await expect(banner).toBeVisible();
  return (await banner.innerText()).replace(/\s+/g, " ");
}

interface BrowserBoard {
  stores: string[];
  jobs: string[];
  outcomes: string[];
}

/**
 * Ask the visitor's own IndexedDB what it holds.
 *
 * The toast is what a person reads; the store is what the claim rests on. A
 * receipt naming the browser while the bytes went elsewhere is the exact lie this
 * change exists to stop, so the test checks both.
 */
async function browserBoard(page: Page): Promise<BrowserBoard> {
  return page.evaluate(async (dbName: string) => {
    const db = await new Promise<IDBDatabase>((resolve, reject) => {
      const request = indexedDB.open(dbName);
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
    const stores = Array.from(db.objectStoreNames);
    const read = (store: string, field: string) =>
      stores.includes(store)
        ? new Promise<string[]>((resolve) => {
            const request = db.transaction(store, "readonly").objectStore(store).getAll();
            request.onsuccess = () =>
              resolve(
                (request.result as Record<string, unknown>[]).map((row) => String(row[field] ?? "")),
              );
            request.onerror = () => resolve([]);
          })
        : Promise.resolve<string[]>([]);

    const board: BrowserBoard = {
      stores,
      jobs: await read("jobs", "name"),
      outcomes: await read("outcomes", "statement"),
    };
    db.close();
    return board;
  }, LOCAL_DB);
}

/** Refuse the board's own endpoints, so the studio has no server to keep them. */
async function keepTheBoardToYourself(page: Page): Promise<void> {
  await page.route(/\/api\/(canvas|jobs|steps|outcomes)([/?#]|$)/, (route) => route.abort());
}

/**
 * Answer the introduction and keep the context.
 *
 * No model is reachable, which is the point: the studio asks its five questions
 * offline, and this save is the first receipt a visitor with no server reads.
 */
async function finishTheContextWizard(page: Page): Promise<string> {
  await page.getByRole("button", { name: "Start with you and your team" }).click();
  const composer = page.getByRole("textbox", { name: COMPOSER });
  for (const answer of CONTEXT_ANSWERS) {
    await composer.fill(answer);
    await composer.press("Enter");
  }
  await expect(page.getByRole("heading", { name: "Does this look like you?" })).toBeVisible();
  await page.getByRole("button", { name: "Looks like me" }).click();
  return receipt(page, "Context saved");
}

/** The first minute, end to end: a job and an outcome, captured by hand. */
async function captureJobAndOutcome(page: Page): Promise<{ job: string; outcome: string }> {
  await offlineNotice(page).getByRole("button", { name: "Capture an outcome" }).click();
  const panel = page.getByRole("complementary", { name: "Capture by hand" });
  await expect(panel).toBeVisible();

  await panel.getByLabel("Job name").fill(JOB);
  await panel.getByRole("button", { name: "Add job" }).click();
  const job = await receipt(page, "Job created");

  await panel.getByLabel("Desired outcome").fill(OUTCOME);
  await panel.getByRole("button", { name: "Record outcome" }).click();
  const outcome = await receipt(page, "Outcome captured");

  return { job, outcome };
}

/**
 * Add the first step, from the job map.
 *
 * The workbench rail lists a view only once that view holds something, so the
 * rail cannot show a job map before a step exists — and creating that first step
 * is the point. `/jobmap` is a command the studio answers without a model, and
 * the job the capture panel just made is the active one.
 */
async function captureStep(page: Page): Promise<string> {
  const composer = page.getByRole("textbox", { name: COMPOSER });
  await composer.fill("/jobmap");
  await composer.press("Enter");
  const map = lens(page);
  await expect(map).toContainText("Universal job map");

  await map.getByRole("button", { name: "Add step" }).click();
  await map.getByLabel("New step name").fill(STEP);
  await map.getByRole("button", { name: "Save" }).click();
  return receipt(page, "Step added");
}

test.describe("a board with no server keeping it", () => {
  test("names the browser in the receipt a visitor can read today", async ({ page }) => {
    await keepTheBoardToYourself(page);
    await openStudio(page, { keepFirstRunDoor: true });

    const saved = await finishTheContextWizard(page);
    expect(saved).toContain(`Context saved. ${KEPT_HERE}`);

    // And the words are true. The studio opened its own store once the server
    // refused the board, and the context it just promised to keep is in this
    // browser rather than on a machine nobody reached.
    expect((await browserBoard(page)).stores).toContain("jobs");
    expect(await page.evaluate(() => window.localStorage.getItem("studio.brief"))).not.toBeNull();
  });
});

test.describe("a board the studio's own sidecar is keeping", () => {
  test.beforeEach(async ({ request }) => {
    await resetRepository(request);
  });

  test("keeps its old copy and claims nothing about the browser", async ({ page }) => {
    await openStudio(page);

    const { job, outcome } = await captureJobAndOutcome(page);
    expect(job).toContain(`Job created: ${JOB}`);
    expect(job).not.toContain(KEPT_HERE);
    expect(outcome).toContain("Outcome captured successfully!");
    expect(outcome).not.toContain(KEPT_HERE);

    const step = await captureStep(page);
    expect(step).toContain("Step added to Job Map!");
    expect(step).not.toContain(KEPT_HERE);

    // Nothing was kept here, because a server was keeping it.
    expect((await browserBoard(page)).jobs).toEqual([]);
  });
});
