/**
 * The origins the browser suite talks to, in one place.
 *
 * `playwright.config.ts` starts the servers on these ports and the helpers call
 * them by origin; a spec never hard-codes one. The MCP-backed sidecar is the
 * only backend that needs an explicit tool URL on every request — it asks the
 * FastMCP server rather than reading the local repository — so the reset has to
 * know which project it is running in.
 */

/** The Studio sidecar on the local backend (the product default). */
export const STUDIO_ORIGIN = "http://127.0.0.1:8100";

/** The second sidecar, on the MCP passthrough backend. */
export const MCP_BACKED_ORIGIN = "http://127.0.0.1:8101";

/** The FastMCP server both sides can reach. */
export const MCP_URL = "http://127.0.0.1:8000/mcp";

/**
 * The tool URL a project's requests must carry, derived from the base URL
 * Playwright is running that project against.
 *
 * The local backend ignores the parameter, so it gets an empty string rather
 * than a URL that would make it ask the MCP server instead of its repository.
 */
export function toolUrlFor(baseURL: string | undefined): string {
  return baseURL === MCP_BACKED_ORIGIN ? MCP_URL : "";
}
