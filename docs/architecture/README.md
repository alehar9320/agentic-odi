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
infra/cloudflare/ Worker script; wrangler.jsonc lives at the repo root
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
- The SPA's conversation runtime is assistant-ui, bound to the Studio's own
  store in `apps/studio/src/assistant/`. That directory
  is the whole bridge: `convert.ts` maps the two message models in both
  directions, `StudioRuntime.tsx` wires the runtime callbacks, and
  `attachments.ts` extracts files in the browser. The library is presentation
  only — it holds no product state and makes no network calls of its own.

## Persistence

- `SQLiteRepository` is the production default for the CLI, MCP server, and Studio API.
- The default database is `~/.agentic-odi/odi.db`, overridable with `AGENTIC_ODI_DB`.
- Studio conversation history and PM memory use a separate SQLite database,
  `~/.agentic-odi/studio.db`, overridable with `AGENTIC_ODI_STUDIO_DB`. They are
  sidecar-local and never enter the ODI repository or the MCP contract.
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

## Related

- [Data flow](data-flow.md)
- [Studio banners](banners.md)
- [Testing](testing.md)
