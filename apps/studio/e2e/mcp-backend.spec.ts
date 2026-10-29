import { expect, test } from "@playwright/test";

import { lens, openStudio } from "./helpers";

/**
 * The Studio against its MCP passthrough backend.
 *
 * With `AGENTIC_ODI_BACKEND=mcp` the sidecar does not read the local
 * repository; it asks the FastMCP server over HTTP and parses what comes
 * back. That is the seam where a tool result can be mistaken for something
 * it is not — a `CallToolResult` is an object, not the text it carries, and
 * the text may be an error rather than a success.
 *
 * These tests run against a second sidecar, on its own port, so they do not
 * disturb the local-backend suite.
 */

const MCP_URL = "http://127.0.0.1:8000/mcp";

/** A job name unique to this run, so the assertions are about our data. */
const JOB_NAME = `E2E MCP Job ${Date.now()}`;

test.describe("the Studio on the MCP backend", () => {
  test.beforeAll(async ({ request }) => {
    const created = await request.post("/api/jobs", {
      data: { name: JOB_NAME, description: "Seeded over MCP", mcp_url: MCP_URL },
    });
    expect(created.ok()).toBeTruthy();
  });

  test("shows the jobs the MCP server holds", async ({ page }) => {
    await openStudio(page);

    // The job picker is rendered from the canvas. Only a canvas hydrated
    // from the MCP server knows about this job; the seed fallback does not.
    await page.getByRole("button", { name: "Capture an outcome" }).click();
    const panel = page.getByRole("complementary", { name: "Capture by hand" });
    await expect(panel.getByLabel("Job", { exact: true })).toContainText(JOB_NAME);
  });

  test("records an outcome through the MCP server", async ({ page, request }) => {
    await openStudio(page);

    await page.getByRole("button", { name: "Capture an outcome" }).click();
    const panel = page.getByRole("complementary", { name: "Capture by hand" });
    await expect(panel).toBeVisible();

    // The job the MCP server already holds is offered in the picker.
    await expect(panel.getByLabel("Job", { exact: true })).toContainText(JOB_NAME);

    await panel
      .getByLabel("Desired outcome")
      .fill("Minimize the time to propagate secrets when rotating credentials");
    await panel.getByRole("button", { name: "Record outcome" }).click();
    await expect(page.getByRole("status").filter({ hasText: "Outcome captured" })).toBeVisible();

    // The outcome really landed in the MCP server.
    const canvas = await request.get(`/api/canvas?mcp_url=${encodeURIComponent(MCP_URL)}`);
    expect(canvas.ok()).toBeTruthy();
    const data = (await canvas.json()) as { source: string; outcomes: { statement: string }[] };
    expect(data.source).toBe("mcp");
    expect(
      data.outcomes.some(
        (outcome) =>
          outcome.statement === "Minimize the time to propagate secrets when rotating credentials",
      ),
    ).toBe(true);
  });

  test("reports a failed write as a failure, not a success", async ({ request }) => {
    // Recording an outcome against a job that does not exist fails inside the
    // MCP server. The Studio must not present that as a success.
    const failed = await request.post("/api/outcomes", {
      data: {
        mcp_url: MCP_URL,
        job_id: "JOB-DOES-NOT-EXIST",
        statement: "Minimize the time to propagate secrets when rotating credentials",
        importance: 9,
        satisfaction: 3,
      },
    });

    expect(failed.status()).toBeGreaterThanOrEqual(400);
    // Failures travel as the sidecar's error envelope, not FastAPI's `detail`.
    const body = (await failed.json()) as { error?: { message?: string } };
    expect(body.error?.message ?? "").toContain("not found");
  });

  test("shows the seeded job in the job map lens", async ({ page }) => {
    await openStudio(page);

    await page.getByRole("button", { name: "Map the job" }).click();
    await expect(lens(page)).toHaveAttribute("aria-label", "Universal job map");
  });
});
