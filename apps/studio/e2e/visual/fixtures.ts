import { expect, type APIRequestContext, type Page } from "@playwright/test";

import { openStudio, rail, resetRepository } from "../helpers";

/**
 * Deterministic fixtures for the screen-level visual harness (issue #547).
 *
 * Every fixture seeds the sidecar repository through the API rather than the
 * UI, so the canvas is fixed before the app boots and a screen never depends
 * on a model or a network call. Each seeded row is labelled as sample data —
 * the canvas is marked as a seed prototype, so the provenance chip renders
 * "DEMO" above the tables instead of passing the fixture off as a user's work.
 */

/** A job, two scored outcomes (one underserved, one served), one unscored
 * outcome, two steps, and two evidence quotes — enough to fill the rail, the
 * landscape, the records lens, and the brief. */
const SAMPLE_OUTCOMES = [
  {
    statement: "Minimize the time to deploy a service when releasing a hotfix",
    importance: 9.2,
    satisfaction: 3.1,
  },
  {
    statement: "Minimize the time to rotate expired tokens when credentials leak",
    importance: 8.0,
    satisfaction: 7.2,
  },
  {
    statement: "Minimize the number of minutes to update the on-call runbook as the platform changes",
    importance: null,
    satisfaction: null,
  },
] as const;

const SAMPLE_EVIDENCE = [
  {
    source_name: "Interview notes",
    source_kind: "interview",
    name: "On-call engineer, 2am",
    content: "A missed key costs a deploy day, and the page is never the same twice.",
    item_type: "note",
  },
  {
    source_name: "Incident log",
    source_kind: "incident",
    name: "Last month's rollback",
    content: "The rollback took forty minutes because the config was hand-copied.",
    item_type: "resource",
  },
] as const;

/**
 * Seed a job, its outcomes, its steps, and two evidence records, then open the
 * Studio. The canvas is marked as a seed prototype by the sidecar, so the
 * provenance chip renders rather than the fixture passing itself off as work.
 */
export async function seedSampleCanvas(
  page: Page,
  request: APIRequestContext,
): Promise<void> {
  await resetRepository(request);

  const job = await request.post("/api/jobs", {
    data: {
      name: "Ship a service to production",
      description: "Platform engineers",
      mcp_url: "",
    },
  });
  expect(job.ok()).toBeTruthy();
  const jobBody = (await job.json()) as { id?: string; result?: { id: string } };
  const jobId = jobBody.id ?? jobBody.result?.id;
  expect(jobId).toBeTruthy();

  for (const outcome of SAMPLE_OUTCOMES) {
    const created = await request.post("/api/outcomes", {
      data: { mcp_url: "", job_id: jobId, ...outcome },
    });
    if (!created.ok()) {
      throw new Error(
        `POST /api/outcomes failed with ${created.status()}: ${await created.text()}`,
      );
    }
  }

  for (const step of [
    { name: "Define the release", order: 1, stage: "define" },
    { name: "Confirm the rollback plan", order: 2, stage: "confirm" },
  ]) {
    const created = await request.post("/api/steps", {
      data: { mcp_url: "", job_id: jobId, ...step },
    });
    if (!created.ok()) {
      throw new Error(
        `POST /api/steps failed with ${created.status()}: ${await created.text()}`,
      );
    }
  }

  for (const evidence of SAMPLE_EVIDENCE) {
    const created = await request.post("/api/evidence", {
      data: { mcp_url: "", job_id: jobId, ...evidence },
    });
    if (!created.ok()) {
      throw new Error(
        `POST /api/evidence failed with ${created.status()}: ${await created.text()}`,
      );
    }
  }

  await openStudio(page);
  // The rail only appears once the canvas has something to look at.
  await expect(rail(page)).toBeVisible();
}

/**
 * Open the landscape lens from the workbench rail. The rail's accessible name
 * is "Your work" and its buttons carry a count, so match on the label prefix.
 * On narrow viewports the rail scrolls horizontally, so the slash command
 * `/landscape` is the reliable route — it is also the keyboard path the
 * brief spec uses to reach the lens without a model.
 */
export async function openLandscape(page: Page): Promise<void> {
  await page.getByRole("textbox", { name: "Message the studio" }).fill("/landscape");
  await page.keyboard.press("Enter");
}

/** The decision brief is the keyboard route that reaches it without a model. */
export async function openBrief(page: Page): Promise<void> {
  await page.getByRole("textbox", { name: "Message the studio" }).fill("/brief");
  await page.keyboard.press("Enter");
}

/** Force a theme before the app boots, the way the Settings panel would. */
export async function setTheme(page: Page, theme: "dark" | "light"): Promise<void> {
  await page.addInitScript((value) => {
    const raw = window.localStorage.getItem("studio.settings");
    const settings = raw ? JSON.parse(raw) : {};
    settings.theme = value;
    window.localStorage.setItem("studio.settings", JSON.stringify(settings));
  }, theme);
}