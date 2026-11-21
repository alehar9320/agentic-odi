import { test as base } from "@playwright/test";

import { resetStudioState } from "./helpers";
import { toolUrlFor } from "./origins";

/**
 * The suite's one piece of shared setup.
 *
 * Playwright starts one sidecar, one repository and one MCP server for the whole
 * run — that is deliberate, because the seam between them is what these tests
 * cover. The cost is that every spec inherits whatever the previous one wrote:
 * jobs, outcomes, evidence, signals, and the conversation memory the app
 * restores on boot. Resetting that per spec, by hand, is the shape of a suite
 * whose result depends on the order Playwright happened to choose (#1118).
 *
 * So the reset is a fixture, marked `auto`, and it runs before every test in
 * every spec that imports `test` from here. A spec that seeds its own canvas
 * still does so in the test body; nothing else carries over.
 *
 * Automatic fixtures are set up before the spec's own `beforeEach` hooks, so a
 * `beforeEach` that seeds through the API is not undone by this reset.
 *
 * Specs must import `test` and `expect` from this module rather than from
 * `@playwright/test`, or they get the shared state back.
 */
export const test = base.extend<{ cleanStudio: void }>({
  cleanStudio: [
    async ({ request, baseURL }, use) => {
      // The MCP-backed project's requests must name the tool server; the local
      // backend's must not. `baseURL` is how the reset knows which it is in.
      await resetStudioState(request, toolUrlFor(baseURL));
      await use();
    },
    { auto: true },
  ],
});

export { expect } from "@playwright/test";
