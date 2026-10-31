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
- `test_service.py` — `ODIService` CRUD, Opportunity Score, and thesis rendering.
- `test_repository.py` — `InMemoryRepository` behavior.
- `test_sqlite_repository.py` — SQLite persistence and round-trips.
- `test_repository_factory.py` — `build_repository()` variant selection.
- `test_schema.py` — schema creation and migration.
- `test_events.py` — event-store schema and legacy-database backfill.
- `test_intent_store.py` — append-only Intent Store ordering.
- `test_pagination.py` — list pagination across both repositories and the service.
- `test_errors.py` — the ODI error hierarchy and its messages.
- `test_evidence_not_found.py` — actionable evidence-not-found errors.
- `test_consent_pause.py` — acting tools wait for PM consent.
- `test_remote.py` — shared MCP tool-result and error parser.
- `test_messages.py` — framework guidelines and shared assistant messages.
- `test_schedule_expr.py` — ISO, relative, and cron parsing, next occurrence, and rejection.
- `test_scheduled_work.py` — schedule CRUD and the truthful "queued for the orchestrator" trigger.

### `apps/mcp-server/tests/`

- `test_tools.py` — the tool surface returns content for each ODI operation.
- `test_odi.py` — end-to-end job/step/outcome workflow through MCP tools.
- `test_parity.py` — the same entity reachable through every tool that touches it.
- `test_context_tools.py` — guidelines, capabilities, and framework context tools.
- `test_customer_outcomes.py` — Customer Outcome and value entities.
- `test_tool_branches.py` — branch coverage for prompts, errors, and full updates.
- `test_server_tools.py` — server-level tool registration and transport wiring.
- `test_tool_spec_validation.py` — startup refuses a contract/registry mismatch.
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
- `test_studio_work.py` — work-item, run, target, and daemon-status routes, redaction, and conflict errors.
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
- `test_schedule_cli.py` — schedule creation, listing, and the queue-for-the-orchestrator trigger.
- `test_orchestrate_cli.py` — `orchestrate` add/list/show/cancel/status/agents and one daemon tick.
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

### `packages/openhands/tests/`

- `test_client.py` — request bodies, auth header variants, status-to-error mapping, redaction, and every Cloud/Agent Server path, all through `httpx.MockTransport`.
- `test_wire_models.py` — start-task and conversation flattening, risk coercion, unknown-event degradation, pending-action rules, and final message/PR extraction.

### `packages/integrations/openhands/tests/`

- `test_orchestrator_models.py` — status sets, target key redaction, confirmation policies, alias uniqueness.
- `test_store.py` — event replay across processes, dedupe by work key, latest run, counts, and daily spend.
- `test_config.py` — config path, `0600` round trip, invalid input, environment overrides, and default lock/heartbeat/workspace paths.
- `test_policy.py` — the deterministic allowlist and denylist: repo-scoped edits, feature-branch pushes, force-push/deletion variants, path traversal and scope escapes, every denied command family, budgets, and the rejection limit.
- `test_service_flow.py` — a fake Cloud + Agent Server cycle: success and PR, quiet polls, confirmation approval, dangerous-action block, hook blocks, retries, crash recovery/adoption, cancellation, schedules, and daily cost caps.
- `test_github_source.py` — labeled-issue intake, pull-request suppression, `ETag`/304, idempotency, reported failures, and terminal labels/comments.
- `test_daemon.py` — single-instance lock, stale/corrupt PID recovery, heartbeat health, recovery notes, signal-driven shutdown, and `--once`.

### Root `tests/`

Cross-package checks only:

- `tests/contract/test_mcp_contract.py` — live FastMCP names, argument names, and required fields match `agentic_odi_core.contract.TOOL_SPECS`.
- `tests/contract/test_cli_contract.py` — the CLI local-handler keys are a subset of `TOOL_NAMES`.
- `tests/test_worker_security_headers.py` — the Living Studio Worker sends its security headers.
- `tests/scripts/test_dev.py`, `test_dev_main.py` — `scripts/dev.py` startup, ports, signals, and shutdown.
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
`machine.test.ts` (state transitions), `service.test.ts` (scheduling,
download, and install), `transport.test.ts` (Tauri boundary), and the
`UpdateBanner`/`UpdateSettings` component tests. `StudioBar.test.tsx` and
`SettingsPanel.test.tsx` cover the UI integration points.

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
