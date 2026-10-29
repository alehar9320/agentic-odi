import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { defineConfig, devices } from "@playwright/test";

/**
 * End-to-end configuration for the Living Studio.
 *
 * The suite drives the real SPA against the real sidecar and MCP server — no
 * mocked network calls — so the tests cover the seams that jsdom and pytest
 * cannot: the SPA's assumptions about the sidecar's response shapes, the
 * sidecar's hydration of the canvas, and the first-run wizard's ordering
 * relative to the rest of the app.
 *
 * The Studio is served by the sidecar from `apps/studio/dist`, so the browser
 * and the API share one origin. Build the SPA before running this suite.
 */
const REPO_ROOT = "../..";
const STUDIO_ORIGIN = "http://127.0.0.1:8100";
const MCP_BACKED_ORIGIN = "http://127.0.0.1:8101";
const MCP_URL = "http://127.0.0.1:8000/mcp";
// Both the repository and the Studio's memory are SQLite files. Give each run
// a private directory so a test never sees another run's canvas, conversations,
// or a schema left behind by an older build.
const E2E_STATE = mkdtempSync(join(tmpdir(), "agentic-odi-e2e-"));

export default defineConfig({
  testDir: "./e2e",
  // The suite shares one sidecar and one repository, so tests must not run
  // concurrently against it.
  workers: 1,
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  timeout: 30_000,
  expect: { timeout: 10_000 },

  use: {
    baseURL: STUDIO_ORIGIN,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },

  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
      testIgnore: /mcp-backend\.spec\.ts/,
    },
    {
      // The same Studio against its MCP passthrough backend, which talks to
      // the FastMCP server over HTTP instead of reading the local
      // repository. This is the path where the tool results have to be
      // parsed rather than taken at face value.
      name: "mcp-backend",
      use: { ...devices["Desktop Chrome"], baseURL: MCP_BACKED_ORIGIN },
      testMatch: /mcp-backend\.spec\.ts/,
    },
  ],

  webServer: [
    {
      // The MCP server answers `GET /mcp` with 406, which Playwright's URL
      // readiness check rejects, so this one is checked by port.
      command: "uv run python -m agentic_odi_mcp_server",
      cwd: REPO_ROOT,
      port: 8000,
      reuseExistingServer: !process.env.CI,
      stdout: "ignore",
      stderr: "pipe",
      timeout: 60_000,
    },
    {
      command: "uv run python -m agentic_odi_studio_api.main",
      cwd: REPO_ROOT,
      url: `${STUDIO_ORIGIN}/health`,
      reuseExistingServer: !process.env.CI,
      stdout: "ignore",
      stderr: "pipe",
      timeout: 60_000,
      env: {
        // Private stores per run, so no test can see another's writes and no
        // stale schema from an earlier build can break the chat path.
        AGENTIC_ODI_DB: join(E2E_STATE, "odi.db"),
        AGENTIC_ODI_STUDIO_DB: join(E2E_STATE, "studio.db"),
        // Point the sidecar at the built SPA explicitly rather than relying on
        // the package-relative path.
        AGENTIC_ODI_STUDIO_DIST: "apps/studio/dist",
      },
    },
    {
      // A second sidecar on the MCP passthrough backend, for the project
      // that exercises the Studio against the FastMCP server.
      command:
        "uv run python -m uvicorn agentic_odi_studio_api.app:create_app --factory --host 127.0.0.1 --port 8101",
      cwd: REPO_ROOT,
      url: `${MCP_BACKED_ORIGIN}/health`,
      reuseExistingServer: !process.env.CI,
      stdout: "ignore",
      stderr: "pipe",
      timeout: 60_000,
      env: {
        AGENTIC_ODI_BACKEND: "mcp",
        AGENTIC_ODI_MCP_URL: MCP_URL,
        AGENTIC_ODI_STUDIO_DB: join(E2E_STATE, "studio-mcp.db"),
        AGENTIC_ODI_STUDIO_DIST: "apps/studio/dist",
      },
    },
  ],
});
