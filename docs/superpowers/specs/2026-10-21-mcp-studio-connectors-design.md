# MCP ↔ Living Studio Connectors — Design

> **Spec for:** `feature/mcp-studio-connectors` (Option A: self-contained local-tool)
> **Spec source:** locked user decisions (shared `~/.config/agentic-odi/connectors.json`, LLM calls a sidecar tool, recommended presets + separate "add custom" flow).

## Intent & Why

Let the Studio copilot register, list, health-check, and forget external MCP/REST/webhook connectors from **conversation**, while also surfacing the same operations in the **Settings UI**. Connectors are persisted to a single shared `connectors.json` so the CLI (`agentic-odi connectors …`) and the Living Studio stay in sync.

## Goals

- One shared resolver for the connector config file (`~/.config/agentic-odi/connectors.json`, override `AGENTIC_ODI_CONNECTORS_CONFIG`).
- Studio Settings UI: list recommended presets, list registered connectors, add from preset/custom, delete, run health check.
- Conversational registration: the LLM calls a local `add_connector` tool; the sidecar persists it and streams a `connector` SSE event to the UI (which renders a suggestion card).
- CLI: `connectors catalog` shows recommended presets; `add`/`health`/`ingest` honor the shared resolver.

## Non-goals / anti-goals

- Do **not** rewire the chat loop to fan out across multiple live MCP servers (leaves that to CGU's later work; merge-time reconcile only).
- Do **not** collide with the in-progress CGU "Conversational Generative UI" in the cwd: B lives on its own worktree off `fix/error-handling-hardening` (pre-CGU), and the local `add_connector` tool + `connector` SSE event is a **clean sibling** of CGU's `render_ui` (no edits to the cwd's CGU files).

## Architecture

```
packages/connectors/            shared config + catalog + registry
  paths.py                      config_path() resolver  (NEW)
  catalog.py                    ConnectorPreset + is_recommended + list_presets(recommended=)
  registry.py                   ConnectorRegistry (already add/list/get) + delete()
apps/cli/                       CLI adapters
  src/.../connectors.py         _config_path() -> reuse paths.config_path()
apps/studio-api/                sidecar (FastAPI)
  src/.../studio/connectors.py  ConnectorService (catalog/add/delete/health) over registry (NEW)
  src/.../studio/router.py      GET/POST/DELETE /api/connectors, /catalog, /{name}/health
  src/.../studio/chat.py        ADD_CONNECTOR_TOOL local tool + `connector` SSE event
  src/.../studio/schemas.py     AddConnectorRequest, ConnectorCatalogItem, ConnectorListItem, ConnectorHealthResponse
  src/.../app.py                app.state.connectors = ConnectorService()
apps/studio/ (frontend)         React + SSE
  src/api/studioApi.ts          connectors(...) REST + streamChat unchanged
  src/types.ts                  ConnectorPreset/Config/Health TS types
  src/state/StudioContext.tsx   connectors state + `connector` SSE → pushToast
  src/components/SettingsPanel.tsx  "Connectors" section
  src/components/chat/ChatCopilot.tsx  `connector` suggestion cards
```

## Contracts

### Shared config (`connectors.json`)
```jsonc
{ "connectors": [ { "name":"gong","kind":"mcp","enabled":true,"settings":{...} } ] }
```
Path resolution: `AGENTIC_ODI_CONNECTORS_CONFIG` env → else `~/.config/agentic-odi/connectors.json`.

### Sidecar API
| Method | Path | Body | Result |
|--------|------|------|--------|
| GET | `/api/connectors/catalog` | — | `[{id,label,area,summary,auth,is_recommended,env_vars,tools,docs}]` (recommended first) |
| GET | `/api/connectors` | — | `[{name,kind,enabled}]` |
| POST | `/api/connectors` | `{name,preset?,url?}` | `{ok:true,name}` |
| DELETE | `/api/connectors/{name}` | — | `{ok:true}` |
| POST | `/api/connectors/{name}/health` | — | `{ok,message,details}` |

### Chat SSE events
- `connector` — `{action:"registered", name, preset?}` / `{status:"error", error}` / `{action:"deleted", name}`.

### Local tool (advertised to LLM)
```js
add_connector({ name?, preset?, url? }) -> { ok, name }
```
Intercepted **in-process** by the sidecar (not sent to the MCP server). On success yields `connector` SSE `registered`; on error yields `connector` SSE `error`.

## CLI
`_config_path()` delegates to `agentic_odi_connectors.paths.config_path`; `catalog` annotates recommended presets; `add mcp --preset <id>` continues to work.

## Merge notes (vs. cwd CGU WIP)
B is built on the **pre-CGU** baseline (b646384). The local-tool interception point (`if entry["name"] == "add_connector"`) and the `connector` SSE `case` are **additions**, not edits, to CGU's `render_ui` path — so the eventual merge needs only a ~10-line dedup, no behavioral conflict.
