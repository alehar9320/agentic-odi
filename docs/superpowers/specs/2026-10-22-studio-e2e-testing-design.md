# End-to-End Testing for the Living Studio — Design

**Date:** 2026-10-22
**Branch:** `feat/e2e-playwright`
**Status:** Approved

## Problem

The Living Studio (`apps/studio/`) is a React SPA driven by the FastAPI sidecar
(`apps/studio-api/`) and, optionally, the FastMCP server (`apps/mcp-server/`).
Today the repository has:

- pytest suites for every Python package (unit + integration, in-memory, fast)
- vitest suites for the SPA's pure functions and components (jsdom)
- a `smoke` CI job that curls the MCP server and the sidecar API

What it does **not** have is a test that drives a real browser against the real
stack. The gap matters because the interesting failures in this codebase live
*between* the layers: the SPA's assumptions about the sidecar's response shape,
the sidecar's hydration of the MCP tool results, and the ordering of the
first-run wizard relative to the rest of the app. Every one of those is
invisible to a jsdom test with a mocked `fetch` and to a pytest test that
constructs the client directly.

## Goals

1. A browser-level test suite that exercises the shipped SPA against the real
   sidecar and MCP server, with no mocked network calls.
2. A CI step that runs it, which can be disabled later **without a code change
   and without a pull request** if it becomes flaky or expensive.
3. No duplication of the existing test stack: reuse the workspace's uv
   tooling, the existing `studio/` npm package, and the existing CI setup
   action.
4. Free to run for an individual developer, on a stock GitHub-hosted runner,
   with no model downloads and no display server.

## Non-goals

- Visual regression testing (pixel diffing). Out of scope; it needs baseline
  images and a stable rendering environment.
- Load or performance testing.
- Replacing the pytest or vitest suites. This layer sits on top of them.
- Native Tauri/Electron UI automation. The desktop shell is a thin wrapper
  around the same SPA; the Tauri build is already covered by `tauri-check`
  and `tauri-build` in CI.

## Framework choice

The research brief referenced vision-language-native frameworks (Midscene.js,
Stagehand, UI-TARS) driving a local model through Ollama, with `xvfb` in CI.

We rejected that for the CI tier, on grounds of cost and determinism:

| | Vision-language agentic | Playwright (chosen) |
|---|---|---|
| Model cost | Needs a local VL model (multi-GB) or a paid endpoint | None — Apache-2.0, free |
| CI requirements | `xvfb`, model warm-up, GPU or slow CPU inference | Plain `npx playwright test` |
| Determinism | Non-deterministic; flaky gates | Deterministic |
| Debuggability | Vision debugger, per-step screenshots | Traces, screenshots, video, HTML report |
| Stack fit | New toolchain, new runtime | Already has Node + npm in `apps/studio` |

The insight worth keeping from that research is **intent-driven locators**: bind
tests to what a user perceives, not to a brittle CSS or XPath selector. Playwright
delivers this natively through accessible-name locators (`getByRole`,
`getByLabel`, `getByText`). The Studio already has the ARIA to support it —
`role="tab"`, `role="log"`, `role="complementary"`, `aria-label`, `<label for>`
— so **no `data-testid` attributes need to be added to the application**.

The Studio has no `data-testid` attributes today, and the E2E suite will not
add any. Every locator in the suite must be a role, label, or visible-text
locator.

## Architecture

```
apps/studio/
├── playwright.config.ts        # Playwright config (new)
├── e2e/                        # E2E specs (new)
│   ├── chat.spec.ts
│   ├── capture.spec.ts
│   ├── landscape.spec.ts
│   └── workspace.spec.ts
└── src/                        # unchanged application code
```

The suite lives inside the `studio/` package because it tests that package's
UI, and because it can then share the package's `node_modules`, its
`tsconfig` project references, its ESLint configuration, and its npm lockfile.
No second npm project and no second lockfile is introduced.

### What the suite talks to

Playwright's `webServer` array starts the real stack. Nothing is mocked:

| Server | Command | Readiness check |
|---|---|---|
| MCP server | `uv run python -m agentic_odi_mcp_server` | `port: 8000` |
| Studio sidecar | `uv run python -m agentic_odi_studio_api.main` | `url: http://127.0.0.1:8100/health` |

Two details are load-bearing:

- **The MCP server is checked by port, not by URL.** `GET /mcp` returns `406`,
  and Playwright's URL readiness check only accepts `2xx`, `3xx`, `400`, `401`,
  `402`, and `403`. A `port` check is the supported alternative.
- **The sidecar serves the built SPA.** `apps/studio-api` resolves
  `apps/studio/dist` at import time and mounts a catch-all route, so the browser
  is served the same origin that serves `/api`. The suite therefore runs
  `npm run build` before `playwright test` and navigates to
  `http://127.0.0.1:8100`. No Vite dev server and no CORS are involved.

`globalSetup` runs after the web servers are up (Playwright orders
`removeOutputDirs → plugin setup (webServer) → global teardown → global setup`),
so it can seed the repository before the first test navigates.

### Backend under test

The Studio API selects its backend with `AGENTIC_ODI_BACKEND`
(`local` — the default — or `mcp`).

The E2E suite exercises the **`local`** backend, because that is the product
default: the sidecar reads the SQLite repository directly through
`fetch_local_canvas`, with no MCP round trip. Each run gets an isolated
database via `AGENTIC_ODI_DB` pointing at a temporary file, so runs are
hermetic and repeatable.

The `mcp` backend is covered by the bug fixes described below and by the
existing `smoke` CI job.

## Bug fixes included

The E2E work surfaced two real defects in the MCP passthrough path. Both are
fixed in this change, because a test suite that encodes broken behaviour is
worse than no test suite.

### Fix A — MCP tool results are never parsed

`apps/studio-api/src/agentic_odi_studio_api/studio/mcp_data.py` reads tool
results with `json.loads(str(raw_jobs))`. But `fastmcp.Client.call_tool()`
returns a `CallToolResult` **object**; `str()` of it is its `repr`, not JSON:

```
CallToolResult(content=[TextContent(type='text', text='[{"id": ...}]')], ...)
```

The parse therefore always raises, the `except` branch sets `jobs = []`, and
`fetch_canvas` always falls back to the seed prototype. The Studio can never
show live MCP data.

The fix extracts the text payload from the result's `content` blocks. The
pattern already exists in this repository at
`packages/connectors/src/agentic_odi_connectors/mcp/connector.py`
(`_content_text`), so the fix follows established house style rather than
inventing a new one.

### Fix B — Tool errors are indistinguishable from success

`call_mcp_tool` returned `str(result)`, so a failed tool call such as
`add_outcome` against a missing job produced a `200 OK` whose body embedded
the literal text `Error: Job with ID JOB-402 not found.` inside a Python repr.
The Studio treats any `2xx` as success and shows **"Outcome captured
successfully!"** while nothing was written.

The same `str(result)` pattern appears in
`apps/studio-api/src/agentic_odi_studio_api/studio/chat.py`, where it is fed
back to the model as the tool result.

Both sites now use the extracted text, so a tool error is a real error.

### Regression coverage

`apps/studio-api/tests/test_studio_mcp_data.py` currently stubs
`call_tool` to return a plain `str`, which is exactly why these defects
survived — the stub does not match the real client's return type. The suite is
extended with a stub that returns a real `CallToolResult`-shaped object, so
the parsing path is covered by a test that mirrors production.

## Test scope

Four spec files, chosen to cover the journeys that cross layer boundaries.

| Spec | Journey |
|---|---|
| `chat.spec.ts` | The composer accepts a message and the assistant replies in the `role="log"` transcript. With no LLM reachable, the reply is the deterministic offline fallback. |
| `capture.spec.ts` | Creating a job and recording an outcome writes through the sidecar into the repository and the new outcome appears in the Landscape. The opportunity-score preview recomputes as the sliders move. |
| `landscape.spec.ts` | The Opportunity Landscape renders metric tiles, outcome cards (`Outcome O-1`), score pills (`🔥 Underserved (Opp: 15.3)`), the underserved-only filter, and the three view modes. |
| `workspace.spec.ts` | The workbench rail opens the Landscape and Job map lenses (`role="complementary"`), marks the active chip with `aria-current="page"`, and closes on `Escape`. |

### Test isolation

Each spec starts from a clean state:

- A fresh browser context per test (Playwright's default) means an empty
  `localStorage`, so the first-run wizard would normally auto-open and block
  the app.
- The wizard is disabled with the `?flags=firstRunWizard:off` query parameter,
  which is the highest-precedence source in `apps/studio/src/features/flags.ts`
  and needs no rebuild.
- The setup conversation is skipped by seeding `studio.setupDismissed`, which
  is what `closeSetup()` writes.
- The repository is a per-run temporary SQLite file, so no test can observe
  another's writes.

## Toolchain integration

Three adjustments keep the new suite from disturbing the existing ones:

1. **Vitest must not collect the E2E specs.** Vitest's default `include` is
   `**/*.{test,spec}.?(c|m)[jt]s?(x)`, which matches `*.spec.ts` anywhere in
   the package. `apps/studio/vite.config.ts` scopes `test.include` to
   `src/**/*.test.{ts,tsx}` so the two runners never overlap.
2. **The E2E specs must be typechecked.** `apps/studio/tsconfig.json` gains a
   `tsconfig.e2e.json` project reference, so the existing `npm run typecheck`
   (`tsc -b --noEmit`) covers the new code.
3. **The E2E artifacts must not be committed.** `apps/studio/.gitignore` gains
   `playwright-report/` and `test-results/`.

`npm run lint` also covers the new directory; the ESLint configuration already
applies to all `**/*.{ts,tsx}` in the package, so the specs are held to the
same standard as the application.

## CI integration

A new `e2e` job in `.github/workflows/ci.yml`:

```yaml
e2e:
  if: ${{ vars.AGENTIC_ODI_E2E != 'false' }}
  continue-on-error: true
```

Two independent kill switches, so the suite can be turned off without touching
code:

- **Repository variable.** Setting `AGENTIC_ODI_E2E=false` in the repository
  settings makes the job skip. `vars` is available in `jobs.<job_id>.if`.
- **`continue-on-error`.** Failures are reported but do not fail the run.

`ci-green` currently requires every job it depends on to report `success`, and
a skipped job reports `skipped`. The check is therefore rewritten to compare
each job's result against its own expectation: `skipped` is acceptable for the
optional `e2e` job, and a failure anywhere else still fails the run.

The job installs the browser with `npx playwright install --with-deps chromium`.
This is free on GitHub-hosted runners and needs no model or display server.

## Alternatives considered

**A separate `e2e/` workspace member (Python + pytest-playwright).** Rejected:
it introduces a second test runner ecosystem, a second lockfile, and a
`pytest-playwright` plugin that lags the first-party runner on fixtures and
reporting. The Studio is a TypeScript package; testing it from the same
package avoids a language boundary in the test code.

**A separate top-level npm project.** Rejected: it duplicates `node_modules`,
the lockfile, the ESLint config, and the TypeScript project references for no
benefit.

**VLM-driven agentic testing (Midscene.js / Stagehand).** Rejected for CI, for
the reasons in the framework comparison. It remains a reasonable future
addition as a *non-gating* exploratory layer, but it cannot be the gate.

**Driving the dev server (`vite`) instead of the built SPA.** Rejected: the dev
server introduces a proxy layer between the browser and `/api`, so the tests
would not exercise the same origin arrangement the product ships with. The
built SPA served by the sidecar is closer to production.

**`data-testid` attributes.** Rejected: the application already exposes
sufficient accessible names, and adding test-only attributes to production
markup is a cost paid by every reader of the component.

## Risks

- **Flakiness from the first-run wizard.** Mitigated by disabling it through the
  documented flag query parameter and by seeding `localStorage` before the app
  boots.
- **Playwright version drift.** The suite pins an exact version in
  `package-lock.json`; the browser build is installed by the pinned CLI, so the
  two stay in step.
- **CI time.** The job installs a browser and builds the SPA. It runs in
  parallel with the existing jobs and is excluded from the `ci-green` gate, so
  it cannot slow the critical path.
