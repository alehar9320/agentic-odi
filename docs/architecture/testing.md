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
- `test_opportunity_score.py` — the ODI opportunity formula, its clamp, and its monotonicity.
- `test_evaluation.py` — the outcome-statement format guard, and the harness that judges a service's scored outcomes by the shared fixture.
- `test_evaluation_harness.py` — a service is judged by `packages/core/tests/fixtures/opportunity-score.json`: a wrong score fails with the id and both values; an unscored outcome stays allowed.
- `test_service.py` — `ODIService` CRUD, Opportunity Score, and thesis rendering.
- `test_repository.py` — `InMemoryRepository` behavior.
- `test_sqlite_repository.py` — SQLite persistence and round-trips.
- `test_repository_factory.py` — `build_repository()` variant selection.
- `test_repository_health.py` — both repositories report store reachability.
- `test_schema.py` — schema creation and migration.
- `test_events.py` — event-store schema and legacy-database backfill.
- `test_intent_store.py` — append-only Intent Store ordering.
- `test_sqlite_integrity.py` — the boot integrity gate, the bounded check, and the clean-shutdown checkpoint.
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
- `test_boot_integrity.py` — the boot failure page, the idle checkpoint, and the clean shutdown that closes both stores.
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
- `test_data_export.py` — `data-export` writes a restorable JSON snapshot.
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
- `test_http_client.py` — the shared HTTP client reads its pool, timeout, and retry settings from the environment.
- `test_rate_limit.py` — token-bucket ingest limits and environment configuration.
- `test_sink.py` — the in-process ingest sink and its rate gate.

### Root `tests/`

Checks that span the workspace rather than one distribution:

- `tests/contract/test_mcp_contract.py` — live FastMCP names, argument names, and required fields match `agentic_odi_core.contract.TOOL_SPECS`.
- `tests/contract/test_cli_contract.py` — the CLI local-handler keys are a subset of `TOOL_NAMES`.
- `tests/test_architecture.py` — the package diagram in the [architecture index](README.md#dependency-direction), the `[project] dependencies` each member declares, and the imports the source actually contains must all agree. It also checks the four groups inside `packages/core`: persistence imports no methodology, and every core module belongs to exactly one group ([the layer table](README.md#inside-packagescore)).
- `tests/test_worker_security_headers.py` — the Living Studio Worker sends its security headers.
- `tests/scripts/test_dev.py`, `test_dev_main.py` — `scripts/dev.py` startup, ports, signals, and shutdown.
- `tests/scripts/test_doc_check.py` — documentation drift: commands, paths, routes, env vars, and README layout.
- `tests/scripts/test_assistant_ui_ledger.py` — the assistant-ui ledger (issue #429): adopted rows cite a merged delivery and name an existing file, counts and the Living Studio projection match the rows.
- `tests/scripts/test_pr_body_gate.py` — CI refuses a branch without a described pull request.
- `tests/scripts/test_release_instructions.py` — release-note section generation.
- `tests/scripts/test_version_sync.py` — the declared version matches the release.

### `brand/tests/` and `website/tests/`

- `brand/tests/test_brand_assets.py`, `test_generated_sources.py` — mascot art and generated brand sources.
- `website/tests/` — static site integrity (`test_site.py`), docs rendering (`test_docs_render.py`), content sync with the repo (`test_content_sync.py`, `test_generated.py`), OG art reproducibility (`test_make_og.py`), the design system (`test_design_system.py`), the Pages deploy (`test_pages_deploy.py`), and the CI wiring that runs this suite (`test_ci_required.py`).

`test_ci_required.py` is the contract that keeps the site from shipping on faith. It asserts the `website` job in `ci.yml` runs `uv run --directory website pytest tests/`, carries no `continue-on-error`, and is both a `needs:` entry and an enforced result in the `CI green` aggregate — the status check the `main-requires-ci-green` ruleset requires. It also asserts the Pages `deploy` job waits on the tested `build`. The wiring has regressed before: the site's checks once lived in a `feature/gh-pages`-only workflow that never ran for a pull request into `main` (402f0a5).

## Isolation Rules

- Use `InMemoryRepository` in tests. `create_app(InMemoryRepository())` keeps the Studio API off the real `~/.agentic-odi/odi.db`.
- The MCP server uses `build_repository()`; tests set `AGENTIC_ODI_DB=:memory:` before import and call tools through `Client(mcp)` without HTTP.
- Async tests use `@pytest.mark.asyncio` (strict mode).

## Coverage

The authoritative Python gate is the `test` job, not Codecov. Pytest runs with
coverage on, and the floor comes from `[tool.coverage.report] fail_under` in
`pyproject.toml` — token-free, so it gates a fork PR the same way it gates
`main`. The current measurement is **89.75%**
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

The outbox drain guard in `apps/studio/src/bff/outbox.ts` is covered by
`outbox.test.ts`, which races two drains twice: once with a `navigator.locks`
stub and once with `navigator.locks` deleted so the lease row runs. Both assert
exactly one send per record, and the lease path also proves a crashed holder's
lease is reclaimed only after it expires and that a running drain renews it.

The IndexedDB schema and its migrations are covered by two files under
`apps/studio/src/bff/store/`. `migrations.test.ts` asserts the registry has a
step for every version up to `DB_VERSION` and that a gap fails with a message
naming the missing version, so raising the version without a migration fails the
suite instead of throwing `ConstraintError` on an existing database.
`indexedDbStore.test.ts` seeds a v1 database with a row in all seven stores,
opens it with the current code, and asserts every row is unchanged and the
migrated schema equals a fresh database's (store names, key paths,
auto-increment flags, and index names). The same file opens a second connection
at a higher version and asserts the first closes and sets `needsReload` instead
of blocking the upgrade.

Copied UI is guarded structurally: `src/vendor/boundary.test.ts` reads every
`.ts` and `.tsx` file under `apps/studio/src/vendor/` and fails on a specifier
that resolves into a product slice (`state`, `api`, `assistant`, `bff`). It is
the second pair of eyes behind the ESLint rule in
`apps/studio/eslint.config.js`, because widening a lint glob silently deletes
the rule. See [Vendor alley](vendor.md).

## Accessibility

Accessibility is tested, not asserted. Four kinds of checks run with the normal
test suites, so a regression turns the build red without a separate command:

- **axe sweep** — `src/test/a11y.test.tsx` renders every shipping surface
  (matrix, job map, catch-up feed, settings, first-run wizard, command palette,
  chat stage, changelog dialog, decision brief) inside a real `<main>` and runs
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

- **artifact structure** — `scripts/artifact_a11y.py` is the one owner of the
  rules an artifact's markup has to satisfy: one `<h1>`, no skipped heading
  level, a named table with scoped headers, a labelled or deliberately hidden
  image, and no id used twice. `tests/scripts/test_artifact_a11y.py` proves each
  rule with a fixture that breaks exactly one of them, `website/tests/test_site.py`
  runs the rule set over every built page, and
  `tests/scripts/test_artifact_inventory.py` scans the artifact roots so a
  renderer nobody registered fails the build by path. The brief is rendered in
  the browser, where Python cannot follow, so `src/components/brief/BriefLens.test.tsx`
  asserts the same four rules against its DOM. Passing these checks is a
  structural statement, not WCAG conformance and not a screen-reader
  certification — that evidence is ALH-252's to collect.

Reduced motion is honoured globally in `theme.css` (`@media
(prefers-reduced-motion: reduce)` collapses animations, transitions, and
`scroll-behavior`), so new components inherit it without opting in.

### Contrast as a build gate

The jsdom sweep above cannot measure contrast, so the browser carries that
half of the gate (issue #543, parent #331). `e2e/a11y.spec.ts` renders the five
core screens — home, the opportunity landscape, the records lens, catch-up, and
settings — in both themes and fails when a screen paints a pair that is not on
the known list, naming the screen, the selector, both colours, and the ratio.
The job is required: `.github/workflows/ci.yml` runs it as `Contrast gate` and
`ci-green` depends on it.

- **the walker** — `src/test/contrast.ts` resolves the effective background by
  walking the ancestors and folding each `background-color` and each gradient
  stop together. axe skips any element over a gradient and returns it as
  `incomplete`, which is exactly the shell, the hero, and the charts, so the
  walker measures them itself and reports a pair it still cannot resolve (an
  image, a filter) as `indeterminate` rather than skipping it. It is
  self-contained: the spec serialises it into the page with
  `Function.prototype.toString`, and `src/test/contrast.test.ts` runs the same
  source in jsdom.
- **the raw-colour gate** — `src/styles/colors.test.ts` fails on a hex or
  `rgb()` literal outside `theme.css`, naming the file and line, so a component
  cannot inline a colour the theme does not own. A handful of files whose
  colours are structural (generated artwork, print media, SVG chart fills) are
  named in `ALLOWED_FILES` with a reason and an issue; the list is capped and
  fails on a stale entry, so it can only shrink.
- **the known pairs** — `e2e/a11y/knownPairs.ts` records the token-level
  failures the walker finds today, each owned by #542 ("fix the tokens that
  fail AA", not yet merged) or #335. It is a ratchet: an unlisted pair fails
  immediately, and an entry that stops failing fails too, so the list can only
  shrink. When #542 lands, the gate reports the stale entries and they are
  deleted.

A deliberately low-contrast pair is injected in the spec's last test, so the
gate is proven to fail rather than assumed to.

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

`first-paint.spec.ts` is the exception to "drives the real sidecar": it aborts
the module bundle so it can read the pre-JavaScript shell in `index.html`, then
compares the colour it painted against the `--bg` token for each theme.

CI runs the suite in the `e2e` job. It is deliberately non-blocking: set the
repository variable `AGENTIC_ODI_E2E` to `false` to skip it, and the
`continue-on-error` on the job keeps a failure from turning CI red.
