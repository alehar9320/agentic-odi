# Testing

## Tiers (pre-PR)
See [`.agents/workflows/test.md`](../../.agents/workflows/test.md):
- `--changed` — PR bar. Runs every required CI check that is a function of the diff.
- `--default` — merge-review bar. Adds repo-wide `mypy`, Studio units/build/bundle budget, and the site build.
- `--full` — CI's responsibility (the local matrix; e2e, Tauri, and the audit stay CI-only).

```bash
uv run python scripts/verify.py --changed
uv run python scripts/verify.py --default
uv run python scripts/verify.py --full
```

The full tier is CI's responsibility and is not asked of anyone before they
open a pull request. The commands below are the reference for what each tier
wraps.

### What the gate covers

`scripts/verify.py` declares, in `CI_JOB_COVERAGE`, which tier covers each job
in `ci-green.needs`, and lists the rest in `CI_ONLY_REASONS` with the reason
they cannot run locally (the dependency audit needs the network; smoke boots
both services; contrast and e2e need Chromium; `tauri-*` need the Rust
toolchain and the webview libraries). It prints that table on every run.
`tests/scripts/test_verify_ci_parity.py` fails when the declaration and
`.github/workflows/ci.yml` disagree, so adding a required job is a two-file
change with a recorded decision, not a silent gap.

A diff that selects no check is a failure. The gate used to print `PASSED`
having run nothing for a studio-only or website-only diff.

## Commands (reference)

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

The root `pyproject.toml` owns pytest, coverage, ruff, mypy, and bandit configuration. There is no per-package test configuration to keep in sync. Coverage floor is enforced in CI (`fail_under = 89`).

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
- `tests/test_worker_error_origin.py` — every Worker-generated failure body carries `origin: "proxy"`, and no failure path bypasses the one factory.
- `tests/scripts/test_dev.py`, `test_dev_main.py` — `scripts/dev.py` startup, ports, signals, and shutdown.
- `tests/scripts/test_doc_check.py` — documentation drift: commands, paths, routes, env vars, and README layout.
- `tests/scripts/test_assistant_ui_ledger.py` — the assistant-ui ledger (issue #429): adopted rows cite a merged delivery and name an existing file, counts and the Living Studio projection match the rows.
- `tests/scripts/test_blind_excepts.py` — every broad `except` under `apps/` and `packages/` logs, or is named in the capped `ALLOWED` baseline with a reason (issue #1091).
- `tests/scripts/test_pr_body_gate.py` — CI refuses a branch without a described pull request.
- `tests/scripts/test_release_instructions.py` — release-note section generation.
- `tests/scripts/test_version_sync.py` — the declared version matches the release.

### `brand/tests/` and `website/tests/`

- `brand/tests/test_brand_assets.py`, `test_generated_sources.py` — mascot art and generated brand sources.
- `website/tests/` — static site integrity (`test_site.py`), docs rendering (`test_docs_render.py`), content sync with the repo (`test_content_sync.py`, `test_generated.py`), OG art reproducibility (`test_make_og.py`), the design system (`test_design_system.py`), the Pages deploy (`test_pages_deploy.py`), and the CI wiring that runs this suite (`test_ci_required.py`).

`test_ci_required.py` is the contract that keeps the site from shipping on faith. It asserts the `website` job in `ci.yml` runs `uv run --directory website pytest tests/`, carries no `continue-on-error`, and is both a `needs:` entry and an enforced result in the `CI green` aggregate — the status check the `main-requires-ci-green` ruleset requires. It also asserts the Pages `deploy` job waits on the tested `build`. The wiring has regressed before: the site's checks once lived in a `feature/gh-pages`-only workflow that never ran for a pull request into `main` (402f0a5).

## Isolation Rules

- Use `InMemoryRepository` in tests. `create_app(InMemoryRepository())` keeps the Studio API off the real `~/.agentic-odi/odi.db`.
- The MCP server builds no store at import. `main()` calls `configure()`; a test calls `configure(InMemoryRepository())` in an autouse fixture and reaches tools through `Client(mcp)` without HTTP.
- Async tests use `@pytest.mark.asyncio` (strict mode).

## Coverage

CI runs the root suite on Python 3.10, 3.11, and 3.12, collects coverage for every `agentic_odi_*` distribution, and uploads `coverage.xml` from the 3.12 job. Codecov requires 90% project coverage; patch coverage is advisory. Python tests and `apps/studio/**` are excluded from the report by `codecov.yml`.

## Frontend

```bash
npm --prefix apps/studio run lint
npm --prefix apps/studio run typecheck
npm --prefix apps/studio test -- --run
npm --prefix apps/studio run build
cd apps/studio/src-tauri && cargo fmt --check && cargo clippy -- -D warnings && cargo check
```

The self-updater lives in `apps/studio/src/updater/` and is covered by vitest:
`machine.test.ts` (state transitions, including the failed-check status line
naming the last *successful* check), `service.test.ts` (scheduling, download,
install, and the bounded in-session action log), `transport.test.ts` (Tauri boundary), and the
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

Reduced motion is honoured globally in `theme.css`: `@media
(prefers-reduced-motion: reduce)` collapses the `--motion-*` duration tokens to
`0ms` and turns off `scroll-behavior`, so a new rule inherits it by reading a
token instead of opting in. Motion driven from JavaScript reads
`useReducedMotion()` (`src/lib/useReducedMotion.ts`), which follows a change
without a reload. The budget is asserted in `src/styles/motion.test.ts`: every
duration outside the token block must be a token, exactly one reduced-motion
rule exists, and only the thinking dots and the streaming caret loop.

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
npm --prefix apps/studio run build            # the sidecar serves apps/studio/dist
npm --prefix apps/studio run test:e2e         # the product suite, chromium + mcp-backend
npm --prefix apps/studio run test:e2e:smoke   # the blocking @smoke subset
npm --prefix apps/studio run test:e2e:visual  # the opt-in screenshot contract
```

Playwright's `webServer` array starts the MCP server, the Studio sidecar, and
a second sidecar on the MCP passthrough backend. `chromium` (the local
backend, the product default) and `mcp-backend` (the passthrough) make up
`test:e2e`. `visual` and `screenshots` are opt-in and run by name.

**A spec is collected by exactly one project.** `chromium` ignores
`mcp-backend.spec.ts`, `visual.spec.ts` and `pr-screenshots.spec.ts`. Before
#1118 it did not ignore the visual spec, so twelve comparisons ran twice, under
two snapshot names, and one contract produced two independent verdicts.

Locators bind to what a user perceives — a role, a label, or visible text —
never to a `data-testid`, of which the application has none, and never to a CSS
class. A class-based locator reports "not visible" when a class moves, which
names the symptom rather than the promise the test was making; a locator that
asserts an attribute one shell happens to set (`aria-label` on the docked lens,
which is labelled by `aria-labelledby`) passes at one viewport and fails at the
other. The two structural handles left are the pre-JavaScript `#boot` shell,
which has no roles because it paints before any script runs, and the
`[role=…]` selector that finds banner rows before `banners()` narrows them to
the one with actions in it — Radix renders each toast twice, as the row a
person sees and as a hidden announcer with the same role and text.

`first-paint.spec.ts` is the exception to "drives the real sidecar": it aborts
the module bundle so it can read the pre-JavaScript shell in `index.html`, then
compares the colour it painted against the `--bg` token for each theme.

### Isolation: one reset, before every test

`e2e/fixtures.ts` exports the `test` and `expect` every spec imports. Its
automatic fixture calls `resetStudioState()` before each test: it deletes every
job (a job takes its steps, outcomes and evidence with it), clears conversation
memory, and dismisses unread signals. The sidecar, its SQLite stores and the
MCP server are shared by the whole run — that is the point of the suite — so
anything a spec leaves behind is state the next spec inherits, and the app
restores the most recent conversation on boot.

The reset used to be hand-rolled per spec, jobs only, with conversation memory
cleared by exactly one file. That made the result depend on the order Playwright
happened to choose, and `/brief` inside a neighbour's thread is what a `brief`
failure looked like (#1118).

A studio that has just been emptied is a studio that has not met the product

yet: it opens the connector offer over the composer, and a modal hides the
composer behind it. `waitForStudioReady()` answers that offer the way a person
would, so a spec that starts from the shared reset reaches the composer without
its own onboarding code. It belongs in the readiness helper for the same reason
the reset belongs in a fixture: a spec that has to remember it is a spec that
will eventually forget (#1118).

### The visual contract is opt-in until it has baselines

`e2e/visual.spec.ts` compares screens with `toHaveScreenshot`, and this
repository has committed no baselines: `e2e/visual.spec.ts-snapshots/` does not
exist. A comparison with no baseline cannot pass, so running it in the product
lane reddened that lane on every push for a reason no test could fix. It is out
of `test:e2e` until its Linux baselines are committed and reviewed;
`npm run test:e2e:visual` writes and compares them with `animations:
"disabled"`, `caret: "hide"` and `scale: "css"` from `playwright.config.ts`.

### The smoke lane blocks a merge; the full suite is signal

CI runs two browser jobs:

- **`e2e-smoke` is required.** It runs the `@smoke`-tagged handful — the settled
  shell, the first run, canvas hydration, one conversation turn, and one boot on
  the MCP backend — with `--retries=0`, so a race fails instead of retiring
  quietly. It has no `continue-on-error` and no repository-variable kill switch:
  turning it off is a code change and a reviewed one.
- **`e2e` is advisory.** It runs the whole suite with `--retries=1` and
  publishes every failure (assertion, locator, call site, attempt count), the
  tests that passed only on retry, and the traces under `test-results/`. Set the
  repository variable `AGENTIC_ODI_E2E` to `false` to skip it, or
  `AGENTIC_ODI_E2E_BLOCKING` to `true` to make it block. It is too broad and too
  slow to be a merge gate on its own, which is why the narrow lane exists.

A retry is recorded, never concealed: `retries: 1` keeps the first attempt's
trace, and the summary names every test that needed the second one.

### A flaky spec is fixed or parked, never retried indefinitely

`e2e/quarantine.ts` is the only way to park one. The spec carries
`// quarantined: #<issue> <YYYY-MM-DD>` in its first twenty lines, and the
ledger carries the issue, the date, and a reason. `src/test/e2eQuarantine.test.ts`
fails when a marker has no entry, an entry has no marker, the two disagree, or
the entry is more than thirty days old. A parked spec still runs, so a fix is
proven by deleting the entry. The list is empty today.

## Observability

Two record shapes are asserted, and both are asserted on their contents rather
than on a line existing:

- `apps/studio-api/tests/test_studio_observability.py` checks the per-turn JSON
  line carries the token counts and the model, that a backend without usage
  leaves the counts `null` (never estimated), and that no API key, bearer token,
  or authorization header reaches a record.
- `apps/studio-api/tests/test_studio_chat_stream.py` drives a usage chunk and a
  backend that rejects `include_usage`, so the fallback path is exercised.
- `apps/mcp-server/tests/test_tool_timing.py` captures one log record per tool
  call and asserts the tool name, the duration key, and — for a failing tool —
  the envelope code the client already branches on.
- `packages/core/tests/test_logging.py` checks the shared `configure_logging()`
  is idempotent: calling it twice does not duplicate a handler.

See [Observability](observability.md) for the two record shapes.
