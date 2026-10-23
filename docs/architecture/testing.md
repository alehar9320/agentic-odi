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

Tests live next to their package (`packages/*/tests`, `apps/*/tests`). Root `tests/` contains only cross-package checks:

- `tests/contract/test_mcp_contract.py` — live FastMCP names, argument names, and required fields match `agentic_odi_core.contract.TOOL_SPECS`.
- `tests/contract/test_cli_contract.py` — the CLI local-handler keys are a subset of `TOOL_NAMES`.
- `tests/scripts/` — dev launcher helpers and lifecycle.

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
