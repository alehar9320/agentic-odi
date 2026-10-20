# Repository Structure Design

**Date:** 2026-10-20

**Status:** Approved

## Intent

Make the repository legible to humans and agents by naming folders after their
functional role, making the dependency direction explicit, and removing
accidental packaging and persistence divergence.

The repository is a Python uv workspace plus a React/Tauri frontend. It currently
has six Python distributions, a frontend, deployment assets, release tooling, and
several agent harness directories at the root. The folder names describe
technology (`core`, `client`, `local_server`) rather than responsibility, so a
new contributor cannot tell what is deployable, what is a library, or who owns
persistence.

## Goals

- Separate deployable applications (`apps/`) from importable libraries
  (`packages/`), infrastructure (`infra/`), packaging, scripts, and docs.
- Give every folder a one-line functional responsibility in
  `docs/architecture/README.md`.
- Replace generic import roots (`core`, `cli`, `client`, `connectors`) with
  unambiguous `agentic_odi_*` package names.
- Remove the dev-only `client` distribution; keep the launcher as
  `scripts/dev.py`.
- Consolidate ruff, mypy, pytest, coverage, and bandit configuration at the
  workspace root; keep only package-specific deltas in package `pyproject.toml`
  files.
- Make the MCP tool contract a single source of truth in core, enforced by a
  cross-package contract test.
- Make SQLite the default persistence for every runtime, with in-memory
  repositories reserved for tests.
- Remove stale repository copies, generated artifacts, and misleading agent
  instructions from the working tree.

## Non-Goals

- No behavioral redesign of the ODI domain model or scoring algorithm.
- No change to the MCP transport (HTTP) or tool semantics.
- No new features in the Studio SPA or Tauri shell.
- No independent release cadence per package. The workspace remains
  single-versioned.
- No rewrite of the CLI command surface beyond import and entry-point updates.

## Constraints

- Python floor stays `>=3.10`; `connectors` must stop targeting 3.11.
- Use the existing `src/` layout and hatchling build backend.
- Keep tests co-located with each package. Root `tests/` holds cross-package
  contract tests only.
- Preserve git history with file moves where practical.
- `/studio` remains a single frontend project containing the Tauri shell.
- The release pipeline, PyInstaller spec, installers, Coverage/Codecov, and
  GitHub workflows must keep working.
- Existing uncommitted work in the tree must not be discarded.

## Target Layout

```text
agentic-odi/
├── apps/
│   ├── cli/                    # agentic-odi-cli -> agentic_odi_cli
│   ├── mcp-server/             # agentic-odi-mcp-server -> agentic_odi_mcp_server
│   ├── studio-api/             # ex-local_server -> agentic_odi_studio_api
│   └── studio/                 # React/Vite SPA + src-tauri
├── packages/
│   ├── core/                   # agentic-odi-core -> agentic_odi_core
│   └── connectors/             # agentic-odi-connectors -> agentic_odi_connectors
├── infra/cloudflare/           # worker.ts + deployment adapter
├── packaging/pyinstaller/
├── scripts/                    # dev.py, build_binary.sh, installers, tests
├── tests/contract/             # cross-package MCP contract tests
├── docs/
│   ├── architecture/           # repo map, data flow, testing
│   ├── reference/              # ODI source-of-truth material
│   └── superpowers/            # specs and plans
├── pyproject.toml              # workspace + shared tooling
├── uv.lock
├── README.md
├── AGENTS.md
└── CHANGELOG.md
```

## Decisions

### Five Python projects, not six

`client` is a development-only process launcher. It has no runtime consumers and
does not justify a distribution, a test suite entry, or a CI step. It becomes
`scripts/dev.py`.

The remaining five distributions stay separate because they have materially
different dependencies and artifacts: the CLI is shipped as a PyInstaller
binary, the MCP server is a protocol adapter, and the Studio API is a FastAPI
sidecar. Consolidating them can be revisited later without changing the folder
roles.

### Import names are versioned by project, not split by namespace

Each distribution uses a distinct top-level import package
(`agentic_odi_core`, `agentic_odi_cli`, etc.) rather than a split
`agentic_odi.*` namespace. This keeps editable installs, PyInstaller hidden
imports, and test imports unambiguous.

### Core owns the MCP contract

Core exposes `contract.py` with tool names and argument models. The MCP server,
CLI backend, and Studio API consume those names instead of duplicating string
literals. A root contract test asserts that the live FastMCP tool registry
matches the contract.

### SQLite is the default persistence for every runtime

The MCP server, CLI, and Studio API instantiate `ODIService` with
`SQLiteRepository` by default. `InMemoryRepository` is test-only. This removes
the current situation where `agentic-odi` local data and data served over MCP
can differ.

### Studio API uses the local service for data, MCP for chat

In local mode, Studio data endpoints read and write through `ODIService` rather
than making an HTTP round trip to the MCP server. The conversational tool loop
continues to use MCP because that is the protocol being exercised. A backend
selector mirrors the CLI's `local|mcp` option.

### Asset paths are configured, not inferred from package depth

The Studio API and dev launcher resolve the SPA directory from
`AGENTIC_ODI_STUDIO_DIST` with a development fallback. They no longer depend on
`parents[3]`, which breaks on every move.

## Migration Phases

1. **Hygiene:** remove the stale `origin/` copy, ignore local worktrees and
   harness state, remove generated artifacts, relocate the ODI reference PDF,
   and fix stale Streamlit instructions.
2. **Tooling:** move shared ruff/mypy/pytest/coverage/bandit config to the root,
   standardize Python 3.10, collapse CI commands.
3. **Python layout:** move core, connectors, cli, mcp_server, and local_server;
   rename import packages and distribution names; update workspace members,
   entry points, PyInstaller, build scripts, CI, and docs.
4. **Launcher:** move the client launcher to `scripts/dev.py` and delete the
   `client` distribution.
5. **Frontend/infra:** move `studio/` to `apps/studio/`, `cloudflare/` to
   `infra/cloudflare/`, and update Vite, Tauri, Wrangler, and release paths.
6. **Contract/persistence:** add the core contract, contract tests, SQLite
   defaults for MCP, Studio API local data path, and architecture docs.

## Verification

Each phase ends with the applicable subset of:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy apps packages
uv run pytest
uv run bandit -c pyproject.toml -r apps packages
npm --prefix apps/studio run typecheck
npm --prefix apps/studio run test
npm --prefix apps/studio run build
bash scripts/build_binary.sh   # VERSION set
```

## Risks

- Import renames touch nearly every test; do the sweep with ripgrep and run the
  full suite before moving on.
- PyInstaller hidden imports and `_build_info.py` paths must be updated with the
  CLI move.
- Tauri and Wrangler configs contain relative asset paths; verify both the web
  build and the desktop config parsing after the frontend move.
- Release workflows reference `scripts/`, `packaging/`, and `cli/src`; update
  them in the same phase as the move.
