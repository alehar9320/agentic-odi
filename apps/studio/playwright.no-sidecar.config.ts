import { defineConfig, devices } from "@playwright/test";

/**
 * The browser suite for the product's most common first run: no sidecar.
 *
 * This is a separate configuration because `webServer` is a top-level option,
 * and the main configuration starts an MCP server and two sidecars. Here there
 * is exactly one process — `vite preview` serving the same `dist` the sidecar
 * job builds — so a test can prove what the Studio does when `/api` is dead.
 *
 * The static preview answers `/api/**` with the SPA shell and status 200, which
 * the client sees as a JSON parse failure. Each test therefore routes `/api/**`
 * to a 503 HTML answer, the shape a dead reverse proxy produces and the shape
 * `isTransportFailure` recognises. Service workers are blocked so that a cached
 * shell cannot answer a navigation or hide the network from the test.
 */
const PREVIEW_ORIGIN = "http://127.0.0.1:4173";

export default defineConfig({
  testDir: "./e2e/no-sidecar",
  testMatch: /no-sidecar\.spec\.ts/,
  // One preview server, one test at a time: the suite asserts on persistence,
  // and a second worker would share the same origin with a different context.
  workers: 1,
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  timeout: 30_000,
  expect: { timeout: 10_000 },

  use: {
    baseURL: PREVIEW_ORIGIN,
    serviceWorkers: "block",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },

  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],

  webServer: {
    command: "npm run preview -- --host 127.0.0.1 --port 4173 --strictPort",
    url: PREVIEW_ORIGIN,
    reuseExistingServer: !process.env.CI,
    stdout: "ignore",
    stderr: "pipe",
    timeout: 60_000,
  },
});
