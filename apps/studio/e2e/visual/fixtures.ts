import { expect, type APIRequestContext } from "@playwright/test";

/**
 * Deterministic screen fixtures for the visual harness.
 *
 * Each fixture seeds the sidecar repository through the API so the Studio
 * paints a known canvas. The seeds are written by hand — no model, no
 * randomness — so every run renders the same pixels.
 *
 * The fixtures are exported as plain functions rather than Playwright
 * fixtures because the spec needs to seed *before* the page opens: the
 * canvas is read from the saved copy on boot, and a page that opens first
 * would paint the empty prototype instead.
 */

export interface SeedJob {
  name: string;
  description?: string;
  steps?: SeedStep[];
  outcomes?: SeedOutcome[];
  evidence?: SeedEvidence[];
}

export interface SeedStep {
  name: string;
  order: number;
}

export interface SeedOutcome {
  statement: string;
  importance: number;
  satisfaction: number;
}

export interface SeedEvidence {
  name: string;
  source_name: string;
  source_kind: string;
  content: string;
  url?: string;
  item_type?: "catalog" | "resource" | "tool_result" | "manual" | "note";
}

/**
 * Seed the repository with a single job, its steps, its outcomes, and the
 * evidence records that back them. Returns the job id.
 */
export async function seedCanvas(
  request: APIRequestContext,
  job: SeedJob,
): Promise<string> {
  const created = await request.post("/api/jobs", {
    data: { name: job.name, description: job.description ?? "", mcp_url: "" },
  });
  expect(created.ok()).toBeTruthy();
  const body = (await created.json()) as { id?: string; result?: { id: string } };
  const jobId = body.id ?? body.result?.id;
  expect(jobId).toBeTruthy();

  for (const step of job.steps ?? []) {
    const stepRes = await request.post("/api/steps", {
      data: {
        mcp_url: "",
        job_id: jobId,
        name: step.name,
        order: step.order,
        allow_empty_job_map: false,
      },
    });
    expect(stepRes.ok()).toBeTruthy();
  }

  for (const outcome of job.outcomes ?? []) {
    const outcomeRes = await request.post("/api/outcomes", {
      data: { mcp_url: "", job_id: jobId, ...outcome },
    });
    expect(outcomeRes.ok()).toBeTruthy();
  }

  for (const record of job.evidence ?? []) {
    const evidenceRes = await request.post("/api/evidence", {
      data: {
        mcp_url: "",
        source_name: record.source_name,
        source_kind: record.source_kind,
        name: record.name,
        content: record.content,
        url: record.url ?? null,
        item_type: record.item_type ?? "manual",
        job_id: jobId,
      },
    });
    expect(evidenceRes.ok()).toBeTruthy();
  }

  return jobId as string;
}

/** A canvas with one underserved outcome and the evidence that backs it. */
export const RECORD_JOB: SeedJob = {
  name: "Deploy a service safely",
  description: "Platform engineers",
  steps: [{ name: "Write the runbook", order: 1 }],
  outcomes: [
    {
      statement: "Minimize the time to deploy a service when releasing a hotfix",
      importance: 9.2,
      satisfaction: 3.1,
    },
  ],
  evidence: [
    {
      name: "On-call incident report",
      source_name: "Incident log",
      source_kind: "manual",
      content:
        "Three deploys in the last month rolled back because the config was copied by hand.",
      url: "https://example.invalid/incidents/2026-03",
      item_type: "tool_result",
    },
  ],
};

/** A canvas with two jobs, so the rail and the landscape both have rows. */
export const MULTI_JOB: SeedJob = {
  name: "Deploy a service safely",
  description: "Platform engineers",
  steps: [{ name: "Write the runbook", order: 1 }],
  outcomes: [
    {
      statement: "Minimize the time to deploy a service when releasing a hotfix",
      importance: 9.2,
      satisfaction: 3.1,
    },
  ],
  evidence: [
    {
      name: "On-call incident report",
      source_name: "Incident log",
      source_kind: "manual",
      content:
        "Three deploys in the last month rolled back because the config was copied by hand.",
      url: "https://example.invalid/incidents/2026-03",
      item_type: "tool_result",
    },
  ],
};