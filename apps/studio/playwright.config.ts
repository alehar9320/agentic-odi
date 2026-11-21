import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { defineConfig, devices } from "@playwright/test";

import { MCP_BACKED_ORIGIN, MCP_URL, STUDIO_ORIGIN } from "./e2e/origins";

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
 *
 * Four rules keep this suite trustworthy (#1118):
 *
 *   1. **One spec, one project.** A spec is collected by exactly one project,
 *      so a test never runs twice under two names and its result is not
 *      double-counted.
 *   2. **`test:e2e` is the product suite.** The pixel-diff project is opt-in
 *      until it has committed baselines; a contract with no baseline cannot
 *      pass, and a lane that can never pass teaches everyone to ignore it.
 *   3. **Every test starts from the same state.** `e2e/fixtures.ts` resets the
 *      shared sidecar before each test, so the result does not depend on the
 *      order Playwright happened to choose.
 *   4. **A retry is recorded, not concealed.** `retries` stays at 1 in CI so a
 *      trace is kept for the first attempt, and the job summary names every
 *      test that passed only on retry.
 */
const REPO_ROOT = "../..";
// Both the repository and the Studio's memory are SQLite files. Give each run
// a private directory so a test never sees another run's canvas, conversations,
// or a schema left behind by an older build.
const E2E_STATE = mkdtempSync(join(tmpdir(), "agentic-odi-e2e-"));

// The sidecar and the MCP server both gate their API with the per-install
// bearer token in one file. The suite stands in for a local client that already
// holds that file, so it writes a private one before the servers start, and the
// same key goes on every request the tests make.
export const E2E_TOKEN = "e2e-sidecar-token";
export const E2E_TOKEN_FILE = join(E2E_STATE, "studio-token");
writeFileSync(E2E_TOKEN_FILE, E2E_TOKEN);

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
  expect: {
    timeout: 10_000,
    // Screenshots are compared only by the opt-in `visual` project. Disabling
    // animation and hiding the caret keeps a comparison about layout and colour
    // rather than about which frame the capture landed on.
    toHaveScreenshot: { animations: "disabled", caret: "hide", scale: "css" },
  },

  use: {
    baseURL: STUDIO_ORIGIN,
    extraHTTPHeaders: { Authorization: `Bearer ${E2E_TOKEN}` },
    // The SPA takes the sidecar token from localStorage, which a real install
    // writes when it launches the app. Seeding it here makes every page boot
    // authenticated, on both origins the suite serves.
    storageState: {
      cookies: [],
      origins: [STUDIO_ORIGIN, MCP_BACKED_ORIGIN].map((origin) => ({
        origin,
        localStorage: [{ name: "studio.token", value: E2E_TOKEN }],
      })),
    },
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },

  projects: [
    {
      // The product suite: everything that drives the shipped app in a browser.
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
      testIgnore: [/mcp-backend\.spec\.ts/, /pr-screenshots\.spec\.ts/, /visual\.spec\.ts/],
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
    {
      // The visual harness: deterministic screens at two sizes, in both themes,
      // with animation disabled. It is a screenshot contract, so it compares
      // every test and keeps the images under version control.
      //
      // It is deliberately NOT part of `npm run test:e2e`. A comparison needs a
      // committed baseline rendered on the same browser build, and this
      // repository has none yet; running it in the product lane made the lane
      // red on every push for a reason no test could fix. It runs when asked
      // for (`npm run test:e2e:visual`), and joins the product lane once its
      // baselines are committed and reviewed.
      name: "visual",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1280, height: 800 },
        // The spec sets the theme per test; this is the baseline the browser
        // starts from when nothing has emulated a scheme yet.
        colorScheme: "dark",
        // A screenshot per test, not just on failure: the harness is the
        // contract, so the baseline is the point.
        screenshot: "on",
      },
      testMatch: /visual\.spec\.ts/,
    },
    // Product screenshots for human review, not a gate. The project is added
    // only when `PR_SCREENSHOTS=1`, so the default run never sees it; the
    // `pr-screenshots` workflow sets the variable and runs the `screenshots`
    // project explicitly.
    ...(process.env.PR_SCREENSHOTS === "1"
      ? [
          {
            name: "screenshots",
            use: { ...devices["Desktop Chrome"] },
            testMatch: /pr-screenshots\.spec\.ts/,
          },
        ]
      : []),
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
      env: { AGENTIC_ODI_STUDIO_TOKEN: E2E_TOKEN_FILE },
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
        AGENTIC_ODI_STUDIO_TOKEN: E2E_TOKEN_FILE,
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
        AGENTIC_ODI_STUDIO_TOKEN: E2E_TOKEN_FILE,
      },
    },
  ],
});
