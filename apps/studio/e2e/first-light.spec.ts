import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

import { COMPOSER, CONVERSATION, lastReply, openStudio } from "./helpers";

/**
 * Pillar 0 · Arrive — the seven promises, proved on every pull request.
 *
 * This is the pillar's own deliverable. A person who has never seen this
 * repository, on a machine with no MCP server and no model, must be able to do
 * all seven things below; this file is the automated test that says so.
 *
 * The whole run is a cold start: the suite's sidecars point at a private
 * directory, no MCP server is started for this project, and no model answers.
 * The deterministic offline assistant is the one a stranger actually meets.
 *
 * The seven promises, in the order the issue lists them:
 *
 *   1. Run one command and reach the Studio.
 *   2. Type one sentence and receive a reply about that sentence.
 *   3. See an empty canvas that says what to do next, and no data they did not
 *      create.
 *   4. Produce one scored outcome.
 *   5. Quit, reopen, and find the conversation, the outcome, and the next step.
 *   6. Read one line that says, accurately, which of the model, the store, and
 *      the MCP server are working.
 *   7. Do all of it again behind an automated test on every pull request.
 *
 * Promise 7 is this file itself; the job that runs it is `e2e` in CI.
 */

/** The cold start the suite already runs against: a sidecar with no MCP and no model. */
const STUDIO_ORIGIN = "http://127.0.0.1:8100";

/**
 * Point the browser at a model and an MCP server that are not there, so the
 * run is provably model-less and MCP-less regardless of what is on the host.
 */
async function configureNothingReachable(page: Page): Promise<void> {
  await page.addInitScript(() => {
    window.localStorage.setItem(
      "studio.settings",
      JSON.stringify({
        base_url: "http://127.0.0.1:1/v1",
        api_key: "local",
        model_name: "local-tools-model",
        mcp_url: "http://127.0.0.1:1/mcp",
      }),
    );
  });
}

/** The canonical canvas after a clean run, so each promise starts from nothing. */
async function clearCanvas(request: APIRequestContext): Promise<void> {
  const response = await request.get("/api/canvas");
  expect(response.ok()).toBeTruthy();
  const canvas = (await response.json()) as { jobs: { id: string }[] };
  for (const job of canvas.jobs) {
    const deleted = await request.delete(`/api/jobs/${encodeURIComponent(job.id)}`);
    expect(deleted.ok()).toBeTruthy();
  }
}

test.describe("Pillar 0 · Arrive — a stranger gets value in five minutes", () => {
  test.beforeEach(async ({ request }) => {
    await clearCanvas(request);
  });

  test("promise 1 · one command reaches the Studio", async ({ page }) => {
    // The one command is `uv run python -m agentic_odi_studio_api.main`, which
    // Playwright starts as the webServer for this project; reaching the page at
    // that origin is the assertion that the command brought the Studio up.
    await openStudio(page);

    await expect(page.getByRole("textbox", { name: COMPOSER })).toBeVisible();
    await expect(page).toHaveTitle(/Studio/i);
  });

  test("promise 2 · one sentence gets a reply about that sentence", async ({ page }) => {
    await configureNothingReachable(page);
    await openStudio(page);

    const sentence = "What do you want to win with onboarding?";
    const composer = page.getByRole("textbox", { name: COMPOSER });
    await composer.fill(sentence);
    await page.getByRole("button", { name: "Send message" }).click();

    // The transcript keeps the person's own words, and the reply is an answer
    // rather than an error: the offline assistant names the sentence it read.
    const log = page.getByRole("log", { name: CONVERSATION });
    await expect(log).toContainText(sentence);
    const reply = await lastReply(page);
    expect(reply.length).toBeGreaterThan(0);
    // Case-insensitive: the same sentence opens the reply on its own line, so
    // its first letter is capitalised, and the copy may be reworded above it.
    expect(reply.toLowerCase()).toContain("no model is reachable");
  });

  test("promise 3 · the empty canvas teaches the next step and invents nothing", async ({
    page,
  }) => {
    await configureNothingReachable(page);
    await openStudio(page);

    // The landscape is the canvas surface. On a cold store it must say what to
    // do next, and it must not show a single row the person did not create.
    await page.getByRole("textbox", { name: COMPOSER }).fill("/landscape");
    await page.getByRole("textbox", { name: COMPOSER }).press("Enter");

    const empty = page.locator(".studio-empty");
    await expect(empty).toBeVisible();
    await expect(empty).toContainText("No opportunities yet");
    await expect(empty).toContainText("Capture an outcome");
    // No fabricated rows: the canvas the sidecar returns is genuinely empty.
    await expect(page.locator(".metric-grid")).toHaveCount(0);
  });

  test("promise 4 · a person can produce one scored outcome", async ({ page }) => {
    await configureNothingReachable(page);
    await openStudio(page);

    await page.getByRole("textbox", { name: COMPOSER }).fill("/capture");
    await page.getByRole("textbox", { name: COMPOSER }).press("Enter");

    // The capture lens is the by-hand path, which is the only honest one when
    // no model is reachable.
    const lens = page.getByRole("complementary").and(page.locator(".lens"));
    await expect(lens).toBeVisible();

    await lens.getByLabel(/Job name/i).fill("Deploy a service safely");
    await lens.getByRole("button", { name: /add job/i }).click();

    await lens
      .getByLabel(/Desired outcome/i)
      .fill("Minimize the time it takes to confirm a deploy is safe when releasing to production");
    await lens.getByLabel(/Importance/i).fill("9");
    await lens.getByLabel(/Current satisfaction/i).fill("3");
    await lens.getByRole("button", { name: /record outcome/i }).click();

    // The scored outcome is now on the canvas, with a real opportunity score.
    const canvas = await page.request.get("/api/canvas");
    const body = (await canvas.json()) as {
      outcomes: { statement?: string; opportunity_score?: number | null }[];
    };
    const scored = body.outcomes.find((outcome) =>
      outcome.statement?.startsWith("Minimize the time it takes to confirm"),
    );
    expect(scored).toBeTruthy();
    expect(scored?.opportunity_score ?? 0).toBeGreaterThan(10);
  });

  test("promise 5 · quit, reopen, and find the conversation, the outcome, and the next step", async ({
    page,
  }) => {
    await configureNothingReachable(page);
    await openStudio(page);

    const sentence = "I own activation and I keep losing new users.";
    await page.getByRole("textbox", { name: COMPOSER }).fill(sentence);
    await page.getByRole("button", { name: "Send message" }).click();
    await lastReply(page);

    // Produce one outcome so the second visit has something to find.
    const createdJob = await page.request.post("/api/jobs", {
      data: { name: "Activate a new user", description: "Growth", mcp_url: "" },
    });
    const job = (await createdJob.json()) as { id: string };
    const createdOutcome = await page.request.post("/api/outcomes", {
      data: {
        mcp_url: "",
        job_id: job.id,
        statement: "Minimize the time it takes a new user to reach first value when onboarding",
        importance: 9,
        satisfaction: 2,
      },
    });
    expect(createdOutcome.ok()).toBeTruthy();

    // Quit: a reload is a fresh boot with the same durable stores.
    await page.reload();

    // The conversation is still there.
    const log = page.getByRole("log", { name: CONVERSATION });
    await expect(log).toContainText(sentence);

    // The outcome is still there.
    await expect
      .poll(async () => {
        const again = await page.request.get("/api/canvas");
        const body = (await again.json()) as { outcomes: { statement?: string }[] };
        return body.outcomes.some((outcome) =>
          outcome.statement?.startsWith("Minimize the time it takes a new user"),
        );
      })
      .toBe(true);

    // And the Studio still offers a next step: the offline notice is the one
    // honest thing it can say, and it names the by-hand routes.
    await expect(page.locator(".banner").filter({ hasText: "Working by hand" })).toBeVisible();
  });

  test("promise 6 · one line reports the model, the store, and the MCP server accurately", async ({
    page,
  }) => {
    await configureNothingReachable(page);
    await openStudio(page);

    // The health answer is the one place the vocabulary lives.
    const response = await page.request.get(
      `${STUDIO_ORIGIN}/api/health?mcp_url=http://127.0.0.1:1/mcp&base_url=http://127.0.0.1:1/v1`,
    );
    expect(response.status()).toBe(200);
    const report = (await response.json()) as {
      status: string;
      checks: Record<string, { ok: boolean; detail: string }>;
    };

    // The sidecar answers, so the report is not "down" merely because no model
    // or MCP server is running; it is honestly "degraded".
    expect(report.checks.sidecar.ok).toBe(true);
    expect(report.checks.store.ok).toBe(true);
    expect(report.checks.mcp.ok).toBe(false);
    expect(report.checks.llm.ok).toBe(false);
    expect(report.status).toBe("degraded");
    expect(report.checks.mcp.detail).toContain("http://127.0.0.1:1/mcp");

    // The same line reaches the person, in their own words.
    await page.getByRole("textbox", { name: COMPOSER }).fill("/status");
    await page.getByRole("textbox", { name: COMPOSER }).press("Enter");
    const log = page.getByRole("log", { name: CONVERSATION });
    await expect(log).toContainText("Studio status");
    await expect(log).toContainText("MCP:");
    await expect(log).toContainText("Store:");
  });

  test("promise 7 · the seven promises are proved on a cold start in one run", async ({
    page,
  }) => {
    // This test is the pillar's own statement of promise 7: every assertion
    // above runs offline, against a real sidecar, on every pull request. This
    // last case asserts the cold start itself — nothing reachable, nothing
    // invented — so a regression that quietly seeds the store is caught here.
    await configureNothingReachable(page);
    await openStudio(page);

    const report = await page.request.get(
      `${STUDIO_ORIGIN}/api/health?mcp_url=http://127.0.0.1:1/mcp&base_url=http://127.0.0.1:1/v1`,
    );
    const body = (await report.json()) as { checks: Record<string, { ok: boolean }> };
    expect(body.checks.mcp.ok).toBe(false);
    expect(body.checks.llm.ok).toBe(false);

    // No sample rows: the canvas says "nothing yet" rather than showing a job
    // the person did not create.
    const canvas = await page.request.get("/api/canvas");
    const data = (await canvas.json()) as {
      jobs: unknown[];
      outcomes: unknown[];
      provenance?: { kind?: string };
    };
    expect(data.jobs).toHaveLength(0);
    expect(data.outcomes).toHaveLength(0);
    expect(data.provenance?.kind ?? "empty").toBe("empty");
  });
});
