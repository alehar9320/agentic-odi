# Testing

## Commands

```bash
uv run pytest                       # all packages + root contract/launcher tests
uv run pytest packages/core         # one package
uv run pytest tests/contract        # MCP contract only
uv run mypy apps packages tests
uv run ruff check .
uv run ruff format --check .
uv run bandit -c pyproject.toml -r apps packages
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

### `apps/mcp-server/tests/`

- `test_tools.py` — the tool surface returns content for each ODI operation.
- `test_odi.py` — end-to-end job/step/outcome workflow through MCP tools.
- `test_parity.py` — the same entity reachable through every tool that touches it.
- `test_context_tools.py` — guidelines, capabilities, and framework context tools.
- `test_customer_outcomes.py` — Customer Outcome and value entities.
- `test_tool_branches.py` — branch coverage for prompts, errors, and full updates.
- `test_server_tools.py` — server-level tool registration and transport wiring.
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
- `test_chat_cli.py`, `test_chat_runtime.py`, `test_chat_wizard.py` — chat command, interactive loop and handlers, and first-run wizard.
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
