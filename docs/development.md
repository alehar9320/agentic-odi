# Development

Everything below mirrors what CI runs. Install the workspace first:

```bash
uv sync --all-packages
```

## Linting, Formatting & Type Checks

```bash
# Ruff lint and formatting checks (per-file config comes from each project's pyproject.toml)
uv run ruff check .
uv run ruff format --check .

# Type checking (run per project so each project's config applies)
uv run --directory core mypy .
uv run --directory mcp_server mypy .
uv run --directory local_server mypy .
uv run --directory client mypy .
uv run --directory cli mypy .
uv run --directory connectors mypy .

# Security scanning
uv run bandit -c pyproject.toml -r core/src mcp_server/src local_server/src cli/src client/src connectors/src
```

## Frontend & Desktop Checks (studio)

The SPA and Tauri shell mirror their CI jobs locally:

```bash
npm --prefix studio run lint       # ESLint
npm --prefix studio run typecheck  # tsc --noEmit
npm --prefix studio test -- --run  # Vitest (run once)
npm --prefix studio run build      # production build → studio/dist
cd studio/src-tauri && cargo fmt --check && cargo clippy -- -D warnings && cargo check
```

## Formatting workflow

- **When editing Python files**, either rely on the **pre-commit hooks** below
  (recommended) or run Ruff formatting directly before pushing:

  ```bash
  uv run ruff format .
  ```

- **CI behavior**:
  - CI runs `uv run ruff check .` to lint without modifying files.
  - CI runs `uv run ruff format --check .` to *verify* formatting only.
  - If CI fails on formatting, run `uv run ruff format .` locally, commit the
    changes, and push again.

## Pre-commit hooks

To run the checks automatically before each commit:

```bash
uv tool install pre-commit
pre-commit install
```

After this, `ruff` and `ruff-format` run on staged files whenever you commit.
You can also trigger them manually:

```bash
pre-commit run --all-files
```

## Testing

Tests use **pytest** with **pytest-asyncio** (strict mode) and run entirely
in-memory — no running server required. Each project owns its tests:

```bash
uv run --directory core pytest
uv run --directory mcp_server pytest
uv run --directory local_server pytest
uv run --directory client pytest
uv run --directory cli pytest
uv run --directory connectors pytest
```

## Test Coverage

CI runs the suite on Python **3.10, 3.11, and 3.12**, combines each package's
coverage into one `coverage.xml`, and uploads it to
[Codecov](https://codecov.io/gh/alehar9320/agentic-odi) from the 3.12 job. Each
matrix job also stores its combined report as a build artifact.

The Codecov upload authenticates with the `CODECOV_TOKEN` repository secret and
is non-blocking (`fail_ci_if_error: false`), so a Codecov outage or a fork PR
without secrets cannot fail the test job. The badge at the top of the README
tracks `main`, which is the baseline every PR is compared against:

- **Project** status requires at least **90%** coverage (`target: 90%`) and
  tolerates a 1% dip from `codecov.yml`.
- **Patch** status is informational for now, so new code can land while the
  suite catches up.

To reproduce the combined report locally, run each package with its own coverage
file and merge them the way CI does:

```bash
set -e
for pkg in core mcp_server local_server client cli connectors; do
  # Absolute path, so each package writes to the repo root rather than its own directory.
  COVERAGE_FILE="$PWD/.coverage.$pkg" uv run --directory "$pkg" pytest --cov="$pkg" -q
done
uv run coverage combine .coverage.*
uv run coverage xml -o coverage.xml && uv run coverage report
```

> [!NOTE]
> Coverage is only collected for the Python packages. `studio/` and test
> directories are excluded in `codecov.yml`.

### Conventions

- Test files live under each project's `tests/` directory and are named
  `test_*.py`.
- Every async test is decorated with `@pytest.mark.asyncio`.
- Use `Client(mcp)` directly (no HTTP server needed) for fast, isolated tests.
- The server's `reset_db` autouse fixture clears in-memory state before each
  test.

### Test Coverage Map

| File | What it covers |
|---|---|
| `core/tests/test_models.py` | Domain models and ODI opportunity-score computation |
| `core/tests/test_service.py` | `ODIService` jobs/steps/outcomes and Customer Outcome CRUD |
| `core/tests/test_sqlite_repository.py` | SQLite event-sourced repository: snapshot reload, updates, deletes, and clear |
| `core/tests/test_intent_store.py` | Append-only Intent Store reads, clear, and legacy blank payloads |
| `core/tests/test_repository.py` | In-memory repository filtering and update/delete edge cases |
| `core/tests/test_messages.py` | Shared framework guidelines and not-found helpers |
| `mcp_server/tests/test_odi.py` | Full ODI workflow (add job → steps → outcomes → retrieval) + capabilities tool |
| `mcp_server/tests/test_customer_outcomes.py` | Customer Outcomes CRUD, filtering, computed opportunity scores, and tool validation |
| `mcp_server/tests/test_server_tools.py` | Error handling and retrieval for the MCP tools |
| `mcp_server/tests/test_tool_branches.py` | Prompt registration, tool validation errors, full updates, and HTTP transport startup |
| `mcp_server/tests/test_tools.py` | Tool response-shape contract for `add_job` |
| `local_server/tests/test_api.py` | Local FastAPI health endpoint |
| `local_server/tests/test_studio_api.py` | Living Studio sidecar API (config, health, canvas, SSE chat, steps/outcomes) |
| `local_server/tests/test_app_spa.py` | SPA fallback, asset mounting, and the uvicorn entrypoint |
| `local_server/tests/test_studio_mcp_data.py` | MCP canvas hydration, seed fallback, and tool passthrough errors |
| `local_server/tests/test_studio_probes.py` | Endpoint probing and LLM health classification |
| `local_server/tests/test_studio_chat_branches.py` | Streaming tool-loop argument and failure branches |
| `local_server/tests/test_studio_router.py` | Successful step/outcome passthrough responses |
| `client/tests/test_run.py` | Dev launcher helpers (port checks, mcp + sidecar commands) |
| `client/tests/test_run_main.py` | Launcher lifecycle: startup errors, polling, signal handlers, and shutdown |
| `studio/src/**/*.test.ts` | SPA units: ODI math, transport bridge, SSE parser, sidecar client |
| `cli/tests/test_cli.py` | CLI `--version`/`version`, help, global options, and unknown-backend handling |
| `cli/tests/test_backend.py` | Local SQLite backend CRUD, remote MCP parsing/errors/timeouts, backend resolution |
| `cli/tests/test_backend_edges.py` | Backend validation messages, full updates, parsing edges, and MCP call failures |
| `cli/tests/test_chat_runtime.py` | Interactive chat loop, streaming, tool-call recovery, and exit paths |
| `cli/tests/test_customer_outcomes_cli.py` | `customer-outcomes` CRUD against SQLite, aliases, human/`--json` output, error exit codes |
| `cli/tests/test_connectors_cli.py` | CLI `connectors` add/list/health/ingest adapter and call timeouts |
| `cli/tests/test_connectors_edges.py` | Connector wrappers, config path resolution, catalog auth types, and error exits |
| `cli/tests/test_onboard.py` | First-run signal extraction, confidence inference, and onboarding gating |
| `cli/tests/test_profile.py` | Baseline load/save/backup, timestamps, and corrupt-file handling |
| `cli/tests/test_update_edges.py` | Update locking, atomic swaps, download failures, and auto-update gating |
| `cli/tests/test_cli_edges.py` | Terminal launch, chat command wiring, and re-exec behavior |
| `cli/tests/test_context.py` | Global backend option and environment fallback |
| `cli/tests/test_render.py` | Human/JSON rendering, truncation, and unicode safety |
| `cli/tests/test_startup_perf.py` | `--version`/`--help` avoid importing fastmcp, connectors, core, and openai |
| `connectors/tests/test_registry.py` | JSON connector registry persist/load and kind checks |
| `connectors/tests/test_mcp_connector.py` | In-memory FastMCP health and ingest records |

> [!TIP]
> Type `/test` in the AI assistant to have the agent run all tests and report the
> results automatically.

## Agent Session Tracking

Agent sessions are captured with the [Entire](https://docs.entire.io/overview)
CLI. The repository integration lives in `.entire/settings.json`,
`.cursor/hooks.json`, and `.opencode/plugins/entire.ts`. Run `entire status` to
confirm it is enabled and `entire checkpoint list` to inspect captured
checkpoints.
