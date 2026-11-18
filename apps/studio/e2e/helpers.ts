import { expect, type APIRequestContext, type Page } from "@playwright/test";

/**
 * Shared helpers for the Living Studio end-to-end suite.
 *
 * Every locator in this suite binds to what a user perceives — a role, a label,
 * or visible text. The Studio exposes enough accessible names for that, so no
 * `data-testid` attributes are needed in the application.
 *
 * Two consequences are load-bearing, and both were learned the hard way (#1118):
 *
 *   - A locator that also requires a CSS class (`.lens`, `.message--assistant`)
 *     reports "not visible" when a class moves, which names the symptom and not
 *     the promise the test was making.
 *   - A locator that asserts an attribute the shell happens to set
 *     (`aria-label` on the docked lens, which uses `aria-labelledby` instead)
 *     passes on one viewport and fails on the other.
 *
 * So: role, label, visible text, or an ARIA role selector where composition
 * needs one. The only structural handles left are the pre-JavaScript shell —
 * which has no roles by definition, because it paints before any script runs.
 */

/** The composer the user types into. */
export const COMPOSER = "Message the studio";

/** The transcript of the conversation. */
export const CONVERSATION = "Conversation";

/**
 * How long the shell may take to become interactive before the boot is called
 * broken. It is generous on purpose: this is the budget for a cold CI runner
 * serving a production build, not for an assertion about app speed.
 */
const READY_TIMEOUT_MS = 15_000;

/**
 * How long to wait for the connector suggestion before deciding a fresh studio
 * is not offering one. The offer renders with the studio's first paint rather
 * than on a timer, so this is a settle window for a slow boot, not a sleep that
 * every test pays.
 */
const SUGGESTION_SETTLE_MS = 2_000;

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
  await waitForStudioReady(page);
  await dismissConnectorSuggestion(page);
}

/**
 * Wait until the app — not the document — is on screen.
 *
 * `#boot` is the shell that paints before any module loads, and React removes
 * it on mount. Waiting for the composer alone would accept the shell's own
 * composer-shaped placeholder if one is ever added; waiting for both is the
 * statement these tests mean: the application has taken over.
 */
export async function waitForStudioReady(page: Page): Promise<void> {
  await expect(page.getByRole("textbox", { name: COMPOSER })).toBeVisible({
    timeout: READY_TIMEOUT_MS,
  });
  await expect(page.locator("#boot")).toHaveCount(0, { timeout: READY_TIMEOUT_MS });
}

/**
 * The connector suggestion dialog, whichever offer it is showing.
 *
 * It renders through the shared `Dialog` primitive (#1004), so its accessible
 * name is the offer's own title ("Connect a suggested system" for an agent
 * suggestion, "Give the studio something to read" for an empty studio). Match
 * the one action every offer carries instead of either title, so the locator
 * survives the copy changing.
 */
export function connectorSuggestion(page: Page) {
  return page
    .getByRole("dialog")
    .filter({ has: page.getByRole("button", { name: "Not now" }) });
}

/**
 * Dismiss the connector suggestion if a fresh studio is offering one. That is
 * real product behavior, so it is dismissed the way a person would.
 */
export async function dismissConnectorSuggestion(page: Page): Promise<void> {
  const suggestion = connectorSuggestion(page);
  // One bounded wait, then one decision. `isVisible()` alone reads the DOM at
  // whatever instant it is called and turns a slow boot into a dialog that
  // opens over the next click.
  const offered = await suggestion
    .waitFor({ state: "visible", timeout: SUGGESTION_SETTLE_MS })
    .then(
      () => true,
      () => false,
    );
  if (!offered) {
    return;
  }
  await suggestion.getByRole("button", { name: "Not now" }).click();
  await expect(suggestion).toBeHidden();
}

/** The workbench rail — the list of views the user can open. */
export function rail(page: Page) {
  return page.getByRole("navigation", { name: "Your work" });
}

/**
 * The docked view (the "lens") that a rail item opens, by its accessible name.
 *
 * The docked lens is labelled with `aria-labelledby` and the mobile sheet with
 * `aria-label`; both resolve to the panel's title, so a role query is the one
 * handle that works in either shell — and it asserts the name a user hears
 * rather than the attribute a particular shell happens to write.
 */
export function lens(page: Page, name: string) {
  // The guidance line is also an `aside` with an accessible name, so it is
  // complementary too; the name keeps the two apart.
  return page.getByRole("complementary", { name, exact: true });
}

/**
 * Whichever lens is open, without naming it.
 *
 * For assertions about the shell rather than the view — "close the lens",
 * "something opened" — where the caller does not know or care which panel it
 * is. The chrome's close control is what makes an `aside` a lens rather than
 * another complementary region.
 */
export function openLens(page: Page) {
  return page
    .getByRole("complementary")
    .filter({ has: page.getByRole("button", { name: "Close workspace view" }) });
}

/**
 * Every banner on screen.
 *
 * Radix renders each one with `role="status"` while it waits and
 * `role="alert"` once the banner system marks it urgent, and it mirrors the
 * text into a hidden live region of its own. Selecting on the role attribute
 * (rather than the rendered class) is what separates the banner from its own
 * announcement, and it keeps working when the banner is restyled.
 */
export function banners(page: Page) {
  return page.locator('[role="status"], [role="alert"]');
}

/**
 * The offline notice, which offers the by-hand routes when no model is
 * reachable.
 */
export function offlineNotice(page: Page) {
  return banners(page).filter({ hasText: "Working by hand" });
}

/** Send a message through the composer and wait for the reply to land. */
export async function sendMessage(page: Page, text: string): Promise<void> {
  const composer = page.getByRole("textbox", { name: COMPOSER });
  await composer.fill(text);
  await page.getByRole("button", { name: "Send message" }).click();
}

/**
 * The assistant replies in the transcript, oldest first.
 *
 * User messages, assistant replies, and notices are all `article` elements, so
 * the role alone does not separate them. The copy action does: it renders only
 * once a reply has finished streaming, which is exactly the set of replies this
 * suite waits for.
 */
export function assistantReplies(page: Page) {
  return page
    .getByRole("log", { name: CONVERSATION })
    .getByRole("article")
    .filter({ has: page.getByRole("button", { name: "Copy reply" }) });
}

/**
 * The text of the most recent assistant reply in the transcript.
 */
export async function lastReply(page: Page): Promise<string> {
  const reply = assistantReplies(page).last();
  await expect(reply).toBeVisible();
  return (await reply.innerText()).trim();
}

/**
 * Empty the repository so each test starts from a known canvas.
 *
 * The sidecar and its repository are shared by the whole run, so a test that
 * left data behind would change what the next one sees. Deleting a job
 * removes the steps and outcomes that belong to it, so clearing the jobs is
 * enough. A job that is already gone is not a failure — the fixture may run
 * twice for one file, and a retry inherits whatever the failed attempt left.
 */
export async function resetRepository(
  request: APIRequestContext,
  toolUrl = "",
): Promise<void> {
  const query = toolUrl ? `?mcp_url=${encodeURIComponent(toolUrl)}` : "";
  const response = await request.get(`/api/canvas${query}`);
  expect(response.ok(), `GET /api/canvas -> ${response.status()}`).toBeTruthy();
  const canvas = (await response.json()) as { jobs: { id: string }[] };

  for (const job of canvas.jobs) {
    const deleted = await request.delete(`/api/jobs/${encodeURIComponent(job.id)}${query}`);
    expect(
      deleted.ok() || deleted.status() === 404,
      `DELETE /api/jobs/${job.id} -> ${deleted.status()}`,
    ).toBeTruthy();
  }
}

/**
 * Forget the conversation the Studio restores on boot.
 *
 * The app opens the most recent thread, so a spec that leaves one behind
 * changes what the next spec sees: a `/brief` command lands inside a stranger's
 * conversation, and the first-run hero never appears. Only `first-run.spec.ts`
 * used to clear this, which made every other spec depend on it having run
 * (#1118).
 */
async function resetMemory(request: APIRequestContext): Promise<void> {
  const response = await request.delete("/api/memory");
  expect(
    response.ok() || response.status() === 404,
    `DELETE /api/memory -> ${response.status()}`,
  ).toBeTruthy();
}

/**
 * Dismiss every signal the store raised.
 *
 * Signals outlive the jobs that produced them, so deleting the canvas does not
 * empty the catch-up inbox; a test that reads "1 unread" inherits yesterday's
 * bump. A backend without a signal inbox answers 404 and nothing needs clearing.
 */
async function resetSignals(request: APIRequestContext, toolUrl: string): Promise<void> {
  // Only unread signals can raise the bell, and the endpoint pages at 50 by
  // default, so ask for the whole unread set in one read.
  const query = [`unread_only=true`, "limit=1000"];
  if (toolUrl) {
    query.push(`mcp_url=${encodeURIComponent(toolUrl)}`);
  }
  const response = await request.get(`/api/signals?${query.join("&")}`);
  if (response.status() === 404) {
    return;
  }
  expect(response.ok(), `GET /api/signals -> ${response.status()}`).toBeTruthy();
  const body = (await response.json()) as { signals?: { id: string }[] } | { id: string }[];
  const signals = Array.isArray(body) ? body : (body.signals ?? []);

  for (const signal of signals) {
    const dismissed = await request.post(`/api/signals/${encodeURIComponent(signal.id)}/dismiss`, {
      // The route's only field: the passthrough backend needs a tool URL to
      // act on, and the local backend ignores it.
      data: { mcp_url: toolUrl },
    });
    expect(
      dismissed.ok() || dismissed.status() === 404,
      `POST /api/signals/${signal.id}/dismiss -> ${dismissed.status()}`,
    ).toBeTruthy();
  }
}

/**
 * Return the shared studio to the state a first visit finds.
 *
 * `e2e/fixtures.ts` runs this before every test, so no spec has to remember it
 * and no spec inherits another's writes.
 */
export async function resetStudioState(
  request: APIRequestContext,
  toolUrl = "",
): Promise<void> {
  await resetRepository(request, toolUrl);
  await resetMemory(request);
  await resetSignals(request, toolUrl);
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
  expect(job.ok(), `POST /api/jobs -> ${job.status()}`).toBeTruthy();
  // The local backend answers with the artifact itself; the passthrough wraps
  // it in `result`. Accept either so the seed does not depend on the backend.
  const jobBody = (await job.json()) as { id?: string; result?: { id: string } };
  const jobId = jobBody.id ?? jobBody.result?.id;
  expect(jobId).toBeTruthy();

  for (const outcome of outcomes) {
    const created = await request.post("/api/outcomes", {
      data: { mcp_url: "", job_id: jobId, ...outcome },
    });
    expect(created.ok(), `POST /api/outcomes -> ${created.status()}`).toBeTruthy();
  }

  return jobId as string;
}
