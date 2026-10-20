# Repository Structure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure the repository into `apps/`, `packages/`, `infra/`, and shared tooling without changing ODI behavior.

**Architecture:** A uv workspace with five Python distributions split into deployable apps and importable libraries, one React/Tauri app, a root tooling configuration, and a core-owned MCP contract. SQLite becomes the default persistence for every runtime.

**Tech Stack:** Python 3.10+, uv, hatchling, ruff, mypy, pytest, FastAPI, FastMCP, Typer, React, Vite, Tauri, PyInstaller.

**Spec:** `docs/superpowers/specs/2026-10-20-repository-structure-design.md`

## Global Constraints

- Python floor is `>=3.10` for every package.
- Import roots are `agentic_odi_core`, `agentic_odi_connectors`, `agentic_odi_cli`, `agentic_odi_mcp_server`, `agentic_odi_studio_api`.
- Tests stay co-located with packages; root `tests/` is contract-only.
- Do not commit changes unless explicitly asked.
- Preserve existing uncommitted work.
- Each phase must end with green lint, typecheck, and tests before the next begins.

## Review Focus

- Any import or entry point still referencing an old module name after the move.
- PyInstaller and release workflows referencing the old `cli/src` path.
- Studio SPA path resolution after the frontend move.
- MCP tools and contract drifting apart.
- Local and MCP backends returning different persisted data.

---

### Task 1: Working-tree hygiene

**Files:**
- Modify: `.gitignore`
- Delete: `origin/` (untracked stale copy)
- Move: `knowledge/Strategyn_what_is_Outcome_Driven_Innovation.pdf` to `docs/reference/`
- Modify: `AGENTS.md`, `.agents/rules/agent_instructions.md`, `.agents/workflows/dev.md`, `.agents/workflows/test.md`

- [ ] Verify `origin/` contains no tracked files or nested git directory.
- [ ] Delete `origin/`.
- [ ] Add `.worktrees/`, `.opencode/plans/`, `.pi/git/`, `.superpowers/`, `.entire/tmp/`, and root coverage/mypy/pytest/ruff caches to `.gitignore`.
- [ ] Move the ODI PDF to `docs/reference/`.
- [ ] Replace stale Streamlit and `client/src/client/app.py` references in agent docs with the current Studio/CLI commands.
- [ ] Update the test workflow commands to the post-migration paths.
- [ ] Verify `git status` shows only intended changes.

### Task 2: Root tooling consolidation

**Files:**
- Modify: `pyproject.toml`
- Modify: `core/pyproject.toml`, `cli/pyproject.toml`, `client/pyproject.toml`, `connectors/pyproject.toml`, `local_server/pyproject.toml`, `mcp_server/pyproject.toml`
- Modify: `.github/workflows/ci.yml`
- Modify: `.agents/workflows/test.md`

- [ ] Set workspace members to `["apps/*", "packages/*"]` (temporarily keep old members until Task 3).
- [ ] Move ruff, mypy, pytest, coverage, and bandit configuration to the root `pyproject.toml`.
- [ ] Remove duplicate tool sections from package `pyproject.toml` files.
- [ ] Change `connectors` target-version and mypy python version to 3.10.
- [ ] Collapse CI lint, typecheck, security, and test commands to root invocations.
- [ ] Run `uv run ruff check .`, `uv run mypy <existing package dirs>`, and `uv run pytest` and confirm green.

### Task 3: Python layout and import rename

**Files:**
- Move: `core/` -> `packages/core/`
- Move: `connectors/` -> `packages/connectors/`
- Move: `cli/` -> `apps/cli/`
- Move: `mcp_server/` -> `apps/mcp-server/`
- Move: `local_server/` -> `apps/studio-api/`
- Rename import roots under each `src/` directory.
- Modify all imports in source and tests.
- Modify workspace members, dependency sources, console scripts, hatch wheel targets.
- Modify `packaging/pyinstaller/odi.spec`, `scripts/build_binary.sh`, `.github/workflows/ci.yml`, `.github/workflows/release.yml`, `codecov.yml`, `README.md`, `studio/package.json`.

- [ ] Move directories.
- [ ] Rename `src/core` -> `src/agentic_odi_core`, etc.
- [ ] Replace imports with `rg` sweep and manual fixes.
- [ ] Update distribution names and `[tool.uv.sources]` keys.
- [ ] Update console scripts: `agentic-odi`, `agentic-odi-server`, `agentic-odi-mcp-server`, `agentic-odi-studio-api`.
- [ ] Update PyInstaller entry, hidden imports, and build-info path.
- [ ] Update CI, release, and Codecov paths.
- [ ] Run `uv sync --all-packages`, lint, mypy, and the full test suite.

### Task 4: Remove the client distribution

**Files:**
- Move: `client/src/client/run.py` -> `scripts/dev.py`
- Move: `client/tests/*` -> `tests/scripts/`
- Delete: `client/`
- Modify: `pyproject.toml`, `scripts/dev.py`, `README.md`, `.agents/*`

- [ ] Move the launcher and adapt paths for the new repo root.
- [ ] Pass `agentic_odi_mcp_server` and `agentic_odi_studio_api` module names to the child processes.
- [ ] Move launcher tests under `tests/scripts/`.
- [ ] Remove the `client` workspace member and CI test step.
- [ ] Update README and agent docs to use `uv run python scripts/dev.py`.
- [ ] Run the launcher tests and full suite.

### Task 5: Frontend and infrastructure move

**Files:**
- Move: `studio/` -> `apps/studio/`
- Move: `cloudflare/` -> `infra/cloudflare/`
- Modify: `wrangler.jsonc`, `apps/studio/src-tauri/tauri.conf.json`, `apps/studio/package.json`, `apps/studio/vite.config.ts`
- Modify: `apps/studio-api/src/agentic_odi_studio_api/app.py`, `scripts/dev.py`
- Modify: `.github/workflows/tauri-release.yml`, `.github/workflows/release.yml`, `README.md`

- [ ] Move the frontend and worker.
- [ ] Introduce `AGENTIC_ODI_STUDIO_DIST` with a development fallback in the Studio API and dev launcher.
- [ ] Update Wrangler asset directory and worker entry.
- [ ] Update Tauri `frontendDist`, `beforeDevCommand`, and `beforeBuildCommand`.
- [ ] Update workflow paths.
- [ ] Run frontend typecheck, tests, build, and Python tests.

### Task 6: Core contract and persistence convergence

**Files:**
- Create: `packages/core/src/agentic_odi_core/contract.py`
- Modify: `packages/core/src/agentic_odi_core/__init__.py`
- Modify: `apps/mcp-server/src/agentic_odi_mcp_server/mcp_server.py`
- Modify: `apps/cli/src/agentic_odi_cli/backend.py`
- Modify: `apps/studio-api/src/agentic_odi_studio_api/studio/mcp_data.py`, `router.py`, `app.py`
- Create: `tests/contract/test_mcp_contract.py`
- Create: `docs/architecture/README.md`, `docs/architecture/data-flow.md`, `docs/architecture/testing.md`
- Modify: `README.md`, `AGENTS.md`

- [ ] Add `TOOL_NAMES` and argument models to core.
- [ ] Replace hardcoded tool names in the CLI and Studio API.
- [ ] Make the MCP server construct a SQLite-backed service by default while keeping an injectable repository for tests.
- [ ] Make Studio data endpoints use the local service when the backend is `local`.
- [ ] Add the MCP contract test.
- [ ] Write the architecture map, data-flow, and testing docs.
- [ ] Update README and AGENTS with the new repo map and commands.
- [ ] Run the full verification suite.

### Task 7: Final verification

- [ ] `uv sync --all-packages --all-extras`
- [ ] `uv run ruff check .`
- [ ] `uv run ruff format --check .`
- [ ] `uv run mypy apps packages`
- [ ] `uv run pytest`
- [ ] `uv run bandit -c pyproject.toml -r apps packages`
- [ ] `npm --prefix apps/studio run typecheck`
- [ ] `npm --prefix apps/studio run test -- --run`
- [ ] `npm --prefix apps/studio run build`
- [ ] Smoke-test `uv run python scripts/dev.py` (ports 8000 and 8100).
- [ ] Build the binary with `VERSION=0.0.0-test bash scripts/build_binary.sh`.
