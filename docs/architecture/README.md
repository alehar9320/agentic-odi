# Repository Architecture

Agentic ODI is a uv workspace with a single root `pyproject.toml` for shared tooling. Python distributions are imported by their stable `agentic_odi_*` package names; directory layout does not leak into imports.

## Layout

```text
apps/
  cli/            agentic_odi_cli         Typer CLI: local SQLite or remote MCP
  mcp-server/     agentic_odi_mcp_server  FastMCP server over HTTP
  studio-api/     agentic_odi_studio_api  FastAPI sidecar for the Studio SPA
  studio/         React + TypeScript + Vite SPA and Tauri 2 shell
packages/
  core/           agentic_odi_core        Domain, services, repositories, contract
  connectors/     agentic_odi_connectors  MCP client connectors and catalog
infra/cloudflare/ Worker + Wrangler config for the free-plan deployment
scripts/          Dev launcher, binary build, installer checks
tests/            Cross-package contract and launcher tests only
docs/             Architecture, reference material, Superpowers artifacts
packaging/        PyInstaller spec for the CLI binary
```

## Dependency Direction

```text
apps/cli ──────────────┐
apps/mcp-server ───────┼──▶ packages/core
apps/studio-api ───────┘         ▲
                                 │
apps/cli ──────────────▶ packages/connectors
```

- `packages/core` depends on no other workspace package.
- `packages/connectors` depends on `core` only where it needs shared models.
- Every runnable app may depend on `core`; none of them imports another app.
- The React SPA only talks to `apps/studio-api` over `/api`; it never calls MCP or the LLM directly.

## Persistence

- `SQLiteRepository` is the production default for the CLI, MCP server, and Studio API.
- The default database is `~/.agentic-odi/odi.db`, overridable with `AGENTIC_ODI_DB`.
- `build_repository()` chooses SQLite by default and `InMemoryRepository` when `AGENTIC_ODI_DB=:memory:`, which is what tests use.
- The CLI selects its backend with `--backend local|mcp` or `AGENTIC_ODI_BACKEND`.
- The Studio API selects `local` (direct service calls) or `mcp` (passthrough) with `AGENTIC_ODI_BACKEND` or `create_app(backend=...)`.

## MCP Contract

`packages/core/src/agentic_odi_core/contract.py` owns `ToolName`, `ToolSpec`, `TOOL_SPECS`, and `TOOL_NAMES`. The live FastMCP registry is asserted against it by `tests/contract/test_mcp_contract.py`; the CLI's local handlers are checked by `tests/contract/test_cli_contract.py`.

## Entry Points

| Command | Module |
|---|---|
| `agentic-odi` | `agentic_odi_cli.cli:app` |
| `agentic-odi-server` / `agentic-odi-mcp-server` | `agentic_odi_mcp_server.mcp_server:main` |
| `agentic-odi-studio-api` | `agentic_odi_studio_api.main:main` |
| `uv run python scripts/dev.py` | Dev launcher (MCP + Studio API) |

## Pull Request Guardrails

`.github/workflows/pr-guardrails.yml` runs three gates on the cumulative
`base...HEAD` diff, so a tree-replacement commit buried in the middle of a
branch is still visible:

- **diff-shape** (blocking): refuses to delete a file that exists on the base
  branch unless it is listed in `.github/pr-guardrails/deletion-allowlist.yml`;
  refuses a diff that deletes more than `max_deletions` lines or changes more
  than `max_changed_files` files, excluding regenerated files. Thresholds live
  in `.github/pr-guardrails/config.yml`.
- **body-truth** (warns; the fenced JSON diff summary blocks): compares
  natural-language file/test claims and the machine-readable block against the
  real diff.
- **fabrication** (warns): flags new `TODO`/`FIXME`/`NotImplementedError`/stubs,
  unconditional `is_available`, hardcoded measurements, and "mock" returns.

The logic lives in `scripts/pr_guards.py`; the YAML only gathers the diff.
Unit tests are in `tests/scripts/test_pr_guards.py`.

Repository ruleset `main-requires-ci-green` (id `25356329`) requires both
`CI green` and `PR guardrails`, sets
`strict_required_status_checks_policy: true`, and keeps the admin bypass only
for pull requests (`bypass_mode: pull_request`). Rulesets are repository
settings, not files; change them with `gh api` and record it here.

## Related

- [Data flow](data-flow.md)
- [Testing](testing.md)
- [Decisions (ADRs)](adr/README.md) — why the architecture looks the way it does
