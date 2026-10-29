# Testing

## Commands

```bash
uv run pytest                       # all packages + root contract/launcher tests
uv run pytest packages/core         # one package
uv run pytest tests/contract        # MCP contract only
uv run mypy apps brand packages
uv run ruff check .
uv run ruff format --check .
uv run bandit -c pyproject.toml -r apps packages
uv run bandit -c pyproject.toml -r website/
```

The root `pyproject.toml` owns pytest, coverage, ruff, mypy, and bandit configuration. There is no per-package test configuration to keep in sync.

## Layout

Tests live next to their package (`packages/*/tests`, `apps/*/tests`). `testpaths` in the root `pyproject.toml` covers `apps`, `brand`, `packages`, `tests`, and `website`, so one `uv run pytest` collects all of them.

### `packages/core/tests/`

- `test_models.py` — domain models and their validation rules.
- `test_job_validation.py` — Job name and description constraints and `create_job()`.
- `test_service.py` — `ODIService` CRUD, Opportunity Score, and thesis rendering.
- `test_repository.py` — `InMemoryRepository` behavior.
- `test_sqlite_repository.py` — SQLite persistence and round-trips.
- `test_repository_factory.py` — `build_repository()` variant selection.
- `test_repository_health.py` — both repositories report store reachability.
- `test_schema.py` — schema creation and migration.
- `test_events.py` — event-store schema and legacy-database backfill.
- `test_intent_store.py` — append-only Intent Store ordering.
- `test_pagination.py` — list pagination across both repositories and the service.
- `test_errors.py` — the ODI error hierarchy and its messages.
- `test_evidence_not_found.py` — actionable evidence-not-found errors.
- `test_consent_pause.py` — acting tools wait for PM consent.
- `test_remote.py` — shared MCP tool-result and error parser.
- `test_connection.py` — MCP timeout and keepalive settings read from the environment.
- `test_messages.py` — framework guidelines and shared assistant messages.

### `apps/mcp-server/tests/`

- `test_tools.py` — the tool surface returns content for each ODI operation.
- `test_odi.py` — end-to-end job/step/outcome workflow through MCP tools.
- `test_parity.py` — the same entity reachable through every tool that touches it.
- `test_context_tools.py` — guidelines, capabilities, and framework context tools.
- `test_customer_outcomes.py` — Customer Outcome and value entities.
- `test_tool_branches.py` — branch coverage for prompts, errors, and full updates.
- `test_server_tools.py` — server-level tool registration and transport wiring.
- `test_tool_spec_validation.py` — startup refuses a contract/registry mismatch.
- `test_health.py` — the `get_health` tool reports accessible and degraded stores.
- `conftest.py` — sets `AGENTIC_ODI_DB=:memory:` before the server imports.

### `apps/studio-api/tests/`

- `test_api.py` — health, config, and canvas bootstrap.
- `test_studio_api.py` — step and outcome passthrough.
- `test_studio_manual_crud.py` — local-backend CRUD from the SPA.
- `test_studio_mcp_data.py` — MCP-backed canvas hydration.
- `test_studio_chat_ui.py` — the `render_ui` local tool in the streaming loop.
- `test_studio_chat_branches.py` — branches of the streaming tool loop.
- `test_studio_brief.py` — onboarding brief reaches the model and the offline fallback.
- `test_studio_connectors.py` — connector registry add, remove, and health.
- `test_studio_connectors_router.py` — connector HTTP routes and catalog.
- `test_studio_memory.py` — conversation memory and recall.
- `test_studio_errors.py` — failures surface as considered errors, not log noise.
- `test_studio_observability.py` — the per-turn structured log line and its redaction.
- `test_studio_probes.py` — endpoint probing and LLM health classification.
- `test_studio_ui_spec.py` — catalog-driven UI validation.
- `test_studio_router.py` — passthrough responses from the Studio router.
- `test_app_spa.py` — static SPA fallback and the local server entrypoint.
- `conftest.py` — shared `InMemoryRepository` fixtures.

### `apps/cli/tests/`

- `test_cli.py`, `test_cli_edges.py` — root commands and their edge cases.
- `test_jobs_cli.py`, `test_steps_cli.py`, `test_desired_outcomes_cli.py`, `test_customer_outcomes_cli.py`, `test_evidence_cli.py` — one file per command group.
- `test_insight_commands.py` — `evaluate`, guidelines, and capabilities on the local backend.
- `test_backend.py`, `test_backend_edges.py`, `test_backend_selection.py` — local vs MCP backend selection and errors.
- `test_context.py` — the global backend context.
- `test_chat_cli.py`, `test_chat_runtime.py`, `test_chat_wizard.py` — chat command, interactive loop and handlers (including reasoning kept out of the answer, and the terminal-only `thinking…` hint), and first-run wizard.
- `test_connectors_cli.py`, `test_connectors_edges.py` — `connectors` subcommands and their edges.
- `test_onboard.py` — first-run onboarding signal extraction and gating.
- `test_update.py`, `test_update_command.py`, `test_update_edges.py`, `test_update_check.py` — update checks and installation.
- `test_profile.py`, `test_paths.py` — config/data directories and `--profile`.
- `test_persistence.py` — every entity survives a fresh repository.
- `test_render.py` — table and JSON rendering.
- `test_mascot.py` — the CLI banner.
- `test_build_info.py` — the version string matches build metadata.
- `test_startup_perf.py` — import-time budget.

### `packages/connectors/tests/`

- `test_catalog.py` — preset catalog contents.
- `test_registry.py` — `connectors.json` persistence.
- `test_factory.py` — building a connector from a config.
- `test_config_path.py` — `AGENTIC_ODI_CONNECTORS_CONFIG` and the default path.
- `test_mcp_connector.py`, `test_rest_connector.py` — MCP and REST ingest.
- `test_mapping.py` — connector records mapped to evidence drafts.
- `test_sink.py` — the in-process ingest sink.

### Root `tests/`

Cross-package checks only:

- `tests/contract/test_mcp_contract.py` — live FastMCP names, argument names, and required fields match `agentic_odi_core.contract.TOOL_SPECS`.
- `tests/contract/test_cli_contract.py` — the CLI local-handler keys are a subset of `TOOL_NAMES`.
- `tests/test_worker_security_headers.py` — the Living Studio Worker sends its security headers.
- `tests/scripts/test_dev.py`, `test_dev_main.py` — `scripts/dev.py` startup, ports, signals, and shutdown.
- `tests/scripts/test_doc_check.py` — documentation drift: commands, paths, routes, env vars, and README layout.
- `tests/scripts/test_roadmap_check.py` — the roadmap gate for new capabilities.
- `tests/scripts/test_pr_body_gate.py` — CI refuses a branch without a described pull request.
- `tests/scripts/test_release_instructions.py` — release-note section generation.
- `tests/scripts/test_version_sync.py` — the declared version matches the release.

### `brand/tests/` and `website/tests/`

- `brand/tests/test_brand_assets.py`, `test_generated_sources.py` — mascot art and generated brand sources.
- `website/tests/` — static site integrity (`test_site.py`), docs rendering (`test_docs_render.py`), content sync with the repo (`test_content_sync.py`, `test_generated.py`), OG art reproducibility (`test_make_og.py`), the design system (`test_design_system.py`), and the Pages deploy (`test_pages_deploy.py`).

## Isolation Rules

- Use `InMemoryRepository` in tests. `create_app(InMemoryRepository())` keeps the Studio API off the real `~/.agentic-odi/odi.db`.
- The MCP server uses `build_repository()`; tests set `AGENTIC_ODI_DB=:memory:` before import and call tools through `Client(mcp)` without HTTP.
- Async tests use `@pytest.mark.asyncio` (strict mode).

## Coverage

The authoritative Python gate is the `test` job, not Codecov. Pytest runs with
`--cov-fail-under=89` on every run, which is token-free and therefore gates a
fork PR the same way it gates `main`. The current measurement is **89.75%**
(7,720 statements, 791 missed). On pull requests, `scripts/coverage_floor.py`
refuses a `pyproject.toml` whose `fail_under` is lower than the base branch's,
so the floor can only ratchet upward. The 3.12 job writes per-distribution
percentages to the job summary and uploads `coverage.xml` to Codecov, which
reports a 90% project target with a 1% dip (the same 89% minimum) and never
fails the build. Patch coverage is advisory.

The Studio is gated by Vitest thresholds instead. `npm run test:coverage`
enforces statements 74, branches 65, functions 75, and lines 74 in
`apps/studio/vite.config.ts`; measured values are 74.18%, 65.38%, 75.49%, and
74.33%. It writes `apps/studio/coverage/lcov.info`, uploaded to Codecov under
the `studio` flag on a non-blocking basis. `scripts/coverage_map.py --check`
keeps the generated map in `docs/development.md` in sync with the test tree.

### Known coverage gaps

Recorded from issue #88 so the holes the coverage map exposes are not hidden.
None of these are fixed by the coverage work itself; they are the next tests to
write.

Python:

- `apps/studio-api/.../studio/changelog.py` measures **27.9%**. The markdown
  parser is only reached through `/api/changelog` with the real `CHANGELOG.md`;
  category headers, commit-link stripping, scoped items, and the
  unparseable-file fallback have no tests of their own.
- `apps/studio-api/.../studio/chat.py` measures **93.0%**. Uncovered: the
  on-device-model fallback branch, a forced remote tier degrading when the
  backend is down, the model stopping mid-stream, and the catch-all turn
  failure handler.
- `packages/core/src/agentic_odi_core/events.py` (**58%**) leaves
  `resolve_device_id` uncovered, including creating the device-id file.
  `intent_store.py` (**68%**) leaves the remote-sync half of the store
  (`insert_remote`, `mark_synced`) uncovered. The MCP server distribution is
  the lowest overall at **81.92%**.

Studio:

- `src/state/StudioContext.tsx` now has a test file, but measures **69% lines
  / 51% branches**. Uncovered SSE dispatcher branches: the `ui` event being
  re-validated, `canvas_dirty` triggering `refreshCanvas()`, and the
  mobile-sheet versus desktop-dock lens split — `useMediaQuery` always returns
  `false` under jsdom, so only one branch runs.
- The least exercised UI modules are `src/ui/catalog.ts` (38% lines / 10%
  branches), `src/ui/primitives.tsx` (23%), `src/components/chat/Markdown.tsx`
  (59%), `src/components/setup/SetupConversation.tsx` (66%), and
  `src/ui/cards.tsx` (70%).
- `src/components/chat/OfflineNotice.tsx` and `src/components/Toasts.tsx` have
  no test of their own. `src/api/schema.d.ts` is generated and imported by
  nothing.
- Issue #88 also listed `StudioContext.tsx`, `StudioBar.tsx`,
  `DirectCapture.tsx`, `EvidenceStream.tsx`, and `OutcomeCard.tsx` as
  untested; each has gained a dedicated test upstream since.

## Frontend

```bash
npm --prefix apps/studio run lint
npm --prefix apps/studio run typecheck
npm --prefix apps/studio test -- --run
npm --prefix apps/studio run test:coverage
npm --prefix apps/studio run build
cd apps/studio/src-tauri && cargo fmt --check && cargo clippy -- -D warnings && cargo check
```

The self-updater lives in `apps/studio/src/updater/` and is covered by vitest:
`machine.test.ts` (state transitions), `service.test.ts` (scheduling,
download, and install), `transport.test.ts` (Tauri boundary), and the
`UpdateBanner`/`UpdateSettings` component tests. `StudioBar.test.tsx` and
`SettingsPanel.test.tsx` cover the UI integration points.

## Accessibility

Accessibility is tested, not asserted. Three kinds of checks run with the normal
frontend suite (`npm --prefix apps/studio test`), so a regression turns the
build red without a separate command:

- **axe sweep** — `src/test/a11y.test.tsx` renders every shipping surface
  (matrix, job map, catch-up feed, settings, first-run wizard, command palette,
  chat stage, changelog dialog) inside a real `<main>` and runs
  [axe-core](https://github.com/dequelabs/axe-core) through `vitest-axe`, with
  zero WCAG 2.1 A/AA violations allowed. The helper lives in `src/test/axe.ts`.
  `vitest-axe@0.1.0` ships an empty `extend-expect` module, so the helper
  asserts on `results.violations` directly instead of the `toHaveNoViolations`
  matcher; the output names the rule, its help text, and the offending
  selector.
  - `color-contrast` is disabled in this sweep: jsdom has no layout, so every
    element computes as transparent-on-white and axe cannot measure real
    colours. Contrast is covered by the next two bullets instead.
- **theme contrast** — `src/styles/theme.test.ts` derives both palettes from
  `theme.css` and asserts every text token (`--text`, `--muted`, `--faint`,
  `--accent`, `--green`, `--amber`) clears 4.5:1 on `--bg` and `--bg-raised`,
  and that the focus ring (`--accent`) clears the 3:1 non-text minimum. The
  same file fails if the stylesheet references a custom property that nothing
  defines, which is how the `--studio-*` aliases silently stopped resolving.
  Measured today: dark text 17.6, muted 8.2, faint 5.1, accent 6.8; light text
  16.6, muted 6.1, faint 4.6, accent 5.0.
- **keyboard and structure** — `src/test/keyboard.test.tsx` asserts the shell
  landmarks, skip link, and `<main>` target, then parses every non-test `.tsx`
  with the TypeScript AST and fails on any intrinsic element that carries
  `onClick` without being a native control or declaring
  `role` + `tabIndex` + `onKeyDown`. Component-level suites cover the rest:
  roving tabindex and arrow keys on the opportunity matrix, `aria-activedescendant`
  in the command palette, focus trapping and focus restore in the mobile lens
  and changelog dialog, and a single polite live region per transcript.

Reduced motion is honoured globally in `theme.css` (`@media
(prefers-reduced-motion: reduce)` collapses animations, transitions, and
`scroll-behavior`), so new components inherit it without opting in.

Contrast is never faked in jsdom: it is computed from the palette tokens above,
and a real-browser axe pass over the matrix, palette, and mobile lens remains a
candidate for the Playwright suite described below, which today covers the
end-to-end seams rather than accessibility.

## End-to-end

The browser-level suite lives in `apps/studio/e2e/` and runs with
[Playwright](https://playwright.dev). It drives the real Studio against the
real sidecar and MCP server — no mocked network calls — so it covers the
seams that neither pytest nor vitest can: the SPA's assumptions about the
sidecar's response shapes, the sidecar's hydration of the canvas, and the
first-run wizard's ordering relative to the rest of the app.

```bash
npm --prefix apps/studio run build      # the sidecar serves apps/studio/dist
npm --prefix apps/studio run test:e2e
```

Playwright's `webServer` array starts the MCP server, the Studio sidecar, and
a second sidecar on the MCP passthrough backend. Two projects run against
them: `chromium` for the local backend (the product default) and
`mcp-backend` for the passthrough.

Locators bind to what a user perceives — a role, a label, or visible text —
never to a `data-testid`, of which the application has none.

CI runs the suite in the `e2e` job. It is deliberately non-blocking: set the
repository variable `AGENTIC_ODI_E2E` to `false` to skip it, and the
`continue-on-error` on the job keeps a failure from turning CI red.
