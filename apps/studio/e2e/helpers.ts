import { expect, type APIRequestContext, type Page } from "@playwright/test";

/**
 * Shared helpers for the Living Studio end-to-end suite.
 *
 * Every locator in this suite binds to what a user perceives — a role, a
 * label, or visible text. The Studio exposes enough accessible names for
 * that, so no `data-testid` attributes are needed in the application.
 */

/** The composer the user types into. */
export const COMPOSER = "Message the studio";

/** The transcript of the conversation. */
export const CONVERSATION = "Conversation";

/**
 * Open the Studio with the first-run wizard and the setup conversation out of
 * the way.
 *
 * The wizard is a full-screen modal that auto-opens on a fresh browser, and
 * the setup conversation replaces the chat until the Studio has a context.
 * Neither is what these tests are about, and both would hide the surfaces
 * under test, so they are switched off the way a QA engineer would: the
 * wizard through its documented query flag, the setup conversation through the
 * same `localStorage` key `closeSetup()` writes.
 *
 * A fresh studio with no connectors also offers one in a modal. That is real
 * product behavior, so it is dismissed the way a user would.
 */
export async function openStudio(page: Page): Promise<void> {
  await page.addInitScript(() => {
    window.localStorage.setItem("studio.setupDismissed", "1");
  });
  await page.goto("/?flags=firstRunWizard:off");
  // The composer is present in both the empty and the active conversation
  // states, so it is the one landmark that means the Studio is ready.
  await expect(page.getByRole("textbox", { name: COMPOSER })).toBeVisible();
  const suggestion = page.getByRole("dialog", { name: "Connector suggestion" });
  await suggestion.waitFor({ state: "visible", timeout: 2_000 }).catch(() => {});
  if (await suggestion.isVisible()) {
    await suggestion.getByRole("button", { name: "Not now" }).click();
    await expect(suggestion).toBeHidden();
  }
}

/** The workbench rail — the list of views the user can open. */
export function rail(page: Page) {
  return page.getByRole("navigation", { name: "Your work" });
}

/** The docked view (the "lens") that a rail item opens. */
export function lens(page: Page) {
  // The guidance line is also an `aside` with an accessible name, so it is
  // complementary too; scope to the docked lens itself.
  return page.getByRole("complementary").and(page.locator(".lens"));
}

/**
 * The offline notice, which offers the by-hand routes when no model is
 * reachable.
 *
 * It is a live region — `status` while the notice is quiet, `alert` once the
 * banner system marks it urgent — and it is the only place outside the hero
 * that offers "Capture an outcome", so scoping to it keeps the two apart.
 */
export function offlineNotice(page: Page) {
  return page
    .getByRole("status")
    .or(page.getByRole("alert"))
    .filter({ hasText: "Working by hand" });
}

/** Send a message through the composer and wait for the reply to land. */
export async function sendMessage(page: Page, text: string): Promise<void> {
  const composer = page.getByRole("textbox", { name: COMPOSER });
  await composer.fill(text);
  await page.getByRole("button", { name: "Send message" }).click();
}

/**
 * The text of the most recent assistant reply in the transcript.
 */
export async function lastReply(page: Page): Promise<string> {
  const replies = page.getByRole("log", { name: CONVERSATION }).locator(".message--assistant");
  const reply = replies.last();
  await expect(reply).toBeVisible();
  // The streaming placeholder is an assistant article too, so wait for the
  // finished state: the copy action only renders once the stream has ended.
  await expect(reply.getByRole("button", { name: "Copy reply" })).toBeVisible();
  return (await reply.innerText()).trim();
}

/**
 * Empty the repository so each test starts from a known canvas.
 *
 * The sidecar and its repository are shared by the whole run, so a test that
 * left data behind would change what the next one sees. Deleting a job
 * removes the steps and outcomes that belong to it, so clearing the jobs is
 * enough.
 */
export async function resetRepository(request: APIRequestContext): Promise<void> {
  const response = await request.get("/api/canvas");
  expect(response.ok()).toBeTruthy();
  const canvas = (await response.json()) as { jobs: { id: string }[] };

  for (const job of canvas.jobs) {
    const deleted = await request.delete(`/api/jobs/${encodeURIComponent(job.id)}`);
    expect(deleted.ok()).toBeTruthy();
  }
}

export interface SeededOutcome {
  statement: string;
  importance: number;
  satisfaction: number;
}

/**
 * Put a job and its outcomes in the repository.
 *
 * The workbench rail only appears once the thread has produced something
 * worth looking at, so a test that exercises the rail needs real artifacts
 * behind it. Seeding through the API rather than the UI keeps the test about
 * the view it is actually checking.
 */
export async function seedOutcomes(
  request: APIRequestContext,
  outcomes: SeededOutcome[],
): Promise<string> {
  const job = await request.post("/api/jobs", {
    data: { name: "Deploy a service safely", description: "Platform engineers", mcp_url: "" },
  });
  expect(job.ok()).toBeTruthy();
  // The local backend answers with the artifact itself; the passthrough wraps
  // it in `result`. Accept either so the seed does not depend on the backend.
  const jobBody = (await job.json()) as { id?: string; result?: { id: string } };
  const jobId = jobBody.id ?? jobBody.result?.id;
  expect(jobId).toBeTruthy();

  for (const outcome of outcomes) {
    const created = await request.post("/api/outcomes", {
      data: { mcp_url: "", job_id: jobId, ...outcome },
    });
    expect(created.ok()).toBeTruthy();
  }

  return jobId as string;
}
