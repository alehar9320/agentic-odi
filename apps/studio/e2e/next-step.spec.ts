import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

import { CONVERSATION, lastReply, openStudio, resetRepository, sendMessage } from "./helpers";

/**
 * The studio remembers why you came back.
 *
 * These tests cover the loop a person actually experiences: a promise written
 * on one visit is spoken back on the next, and answering it changes the
 * repository. No model is reachable during the run, so a turn that put a
 * surface on the screen — the trigger for *offering* to remember something —
 * cannot happen here; the promise is seeded through the API instead and the
 * browser exercises the answering half. Everything asserted below is read back
 * through the sidecar, because the store is what the next visit will read.
 */

/** What every test here says to start the thread. */
const OPENING = "What would have to be true for that?";

interface OpenStep {
  id: string;
  text: string;
  due_at?: string | null;
}

interface EvidenceRecord {
  name: string;
  content: string;
}

async function seedPromise(request: APIRequestContext, text: string): Promise<void> {
  const created = await request.post("/api/next-step", { data: { text, mcp_url: "" } });
  expect(created.ok()).toBeTruthy();
}

/** The one step the store still considers outstanding, or `null`. */
async function openStep(request: APIRequestContext): Promise<OpenStep | null> {
  const response = await request.get("/api/next-step?mcp_url=");
  expect(response.ok()).toBeTruthy();
  return (await response.json()) as OpenStep | null;
}

async function evidenceFor(
  request: APIRequestContext,
  promise: string,
): Promise<EvidenceRecord[]> {
  const response = await request.get("/api/evidence?mcp_url=");
  expect(response.ok()).toBeTruthy();
  const body = (await response.json()) as { result: EvidenceRecord[] };
  return body.result.filter((record) => record.name.includes(promise));
}

/**
 * Arrive on the empty stage, whatever the shared sidecar still holds.
 *
 * The greeting only lives on the empty stage and the Studio resumes the latest
 * conversation on load, so a visit that has to start with the headline has to
 * leave the resumed thread first. The control is disabled when there is nothing
 * to leave, which is the state this visit already wanted.
 */
async function startVisit(page: Page): Promise<void> {
  await openStudio(page);
  const fresh = page.getByRole("button", { name: "Start a new thread" });
  if (await fresh.isEnabled()) {
    await fresh.click();
  }
  await expect(page.locator(".hero__line")).toBeVisible();
}

/**
 * A thread with a reply in it.
 *
 * The question lives in the dock, and the dock only exists once the transcript
 * has started. So every test here says something first.
 */
async function startThread(page: Page): Promise<void> {
  await sendMessage(page, OPENING);
  await lastReply(page);
}

function question(page: Page) {
  return page.getByRole("complementary", { name: "What you said you would do" });
}

test.describe("the next step", () => {
  test.beforeEach(async ({ request }) => {
    await resetRepository(request);
  });

  test("asks about the promise on both screens and keeps the answer as evidence", async ({
    page,
    request,
  }) => {
    const promise = "talk to two support leads about the manual queue";
    await seedPromise(request, promise);
    await startVisit(page);

    await expect(page.locator(".hero__line")).toContainText(
      `Last time you said you would ${promise}`,
    );

    await startThread(page);
    await expect(question(page)).toContainText(`“${promise}” — did it happen?`);

    await question(page).getByRole("button", { name: "Yes" }).click();
    await question(page).getByLabel("What happened?").fill("Both said the queue is manual today");
    await question(page).getByRole("button", { name: "Keep it as evidence" }).click();

    await expect(question(page)).toBeHidden();
    await expect.poll(() => openStep(request)).toBeNull();
    const records = await evidenceFor(request, promise);
    expect(records).toHaveLength(1);
    expect(records[0].content).toBe("Both said the queue is manual today");
  });

  test("writes nothing for an answer that only says not yet", async ({ page, request }) => {
    const promise = "read the churn calls from March";
    await seedPromise(request, promise);
    await startVisit(page);
    await startThread(page);

    await question(page).getByRole("button", { name: "Not yet" }).click();
    expect((await openStep(request))?.text).toBe(promise);
    expect(await evidenceFor(request, promise)).toHaveLength(0);
  });

  test("keeps a promise quiet for the rest of the visit", async ({ page, request }) => {
    const promise = "review the reconciliation query with billing";
    await seedPromise(request, promise);
    await startVisit(page);
    await startThread(page);

    await question(page).getByRole("button", { name: "Not yet" }).click();
    await question(page).getByRole("button", { name: "Keep asking" }).click();
    await expect(question(page)).toBeHidden();

    // A reload resumes this thread, so the dock is on screen again and the quiet
    // has to hold: it was promised for the visit, not for the click.
    await openStudio(page);
    await expect(page.getByRole("log", { name: CONVERSATION })).toContainText(OPENING);
    await expect(question(page)).toHaveCount(0);

    // A new thread puts the headline back where the same ask also lives.
    await page.getByRole("button", { name: "Start a new thread" }).click();
    await expect(page.locator(".hero__line")).toContainText("What do you want to win?");

    expect((await openStep(request))?.text).toBe(promise);
    expect(await evidenceFor(request, promise)).toHaveLength(0);
  });

  test("closes a dropped promise without manufacturing an answer", async ({ page, request }) => {
    const promise = "ask the billing engineer for the reconciliation query";
    await seedPromise(request, promise);
    await startVisit(page);
    await startThread(page);

    await question(page).getByRole("button", { name: "Not yet" }).click();
    await question(page).getByRole("button", { name: "Drop it" }).click();

    await expect(question(page)).toBeHidden();
    await expect.poll(() => openStep(request)).toBeNull();
    expect(await evidenceFor(request, promise)).toHaveLength(0);
  });

  test("moves the promise to a date instead of closing it", async ({ page, request }) => {
    const promise = "sit with a recruiter on the first upload";
    await seedPromise(request, promise);
    await startVisit(page);
    await startThread(page);

    await question(page).getByRole("button", { name: "Not yet" }).click();
    await question(page).getByRole("button", { name: "Later" }).click();
    await question(page).getByLabel("Ask again on").fill("2026-12-01");
    await question(page).getByRole("button", { name: "Set the date" }).click();

    // The store refuses a reminder with no timezone, and the browser is the one
    // that has to add it, so compare against the same midnight read in this page.
    const expected = await page.evaluate(() => new Date("2026-12-01T00:00:00").getTime());
    await expect
      .poll(async () => {
        const step = await openStep(request);
        return step?.due_at ? new Date(step.due_at).getTime() : null;
      })
      .toBe(expected);
    await expect(question(page)).toContainText(promise);
    expect(await evidenceFor(request, promise)).toHaveLength(0);
  });
});
