# Data Flow

## Sources of Truth

| Layer | Owns | Persists |
|---|---|---|
| `packages/core` | `Job`, `Step`, `Outcome`, `CustomerOutcome`, `ODIService`, repository protocol | SQLite event log + snapshots |
| `apps/mcp-server` | MCP tool adapters over `ODIService` | `build_repository()` selects SQLite in production and in-memory for `AGENTIC_ODI_DB=:memory:` |
| `apps/studio-api` | Studio API, canvas projection, chat tool loop | Via the same repository when the local backend is active |
| `packages/connectors` | Connector protocol, presets, and record mapping | Connector configuration and ingest batches |
| `apps/studio` | Presentation state, optimistic canvas updates | Browser cache only |
| `apps/cli` | Terminal rendering, local/remote backend selection | SQLite directly for `local`, no local writes for `mcp` |

## Write Paths

### Local CLI

```text
agentic-odi customer-outcomes add
  -> LocalBackend
  -> ODIService
  -> SQLiteRepository
  -> IntentStore (append) + snapshot refresh
```

### MCP

```text
MCP client / Studio MCP mode / CLI --backend mcp
  -> FastMCP tool
  -> ODIService
  -> configured Repository
```

`apps/mcp-server` builds its repository once at import time with `build_repository()`. Production uses SQLite; tests set `AGENTIC_ODI_DB=:memory:` (the root test suite does this in `tests/conftest.py`).

### Studio API

```text
apps/studio SPA
  -> /api/canvas, /api/steps, /api/outcomes
  -> backend=local: ODIService -> Repository
  -> backend=mcp:   call_mcp_tool -> MCP server -> ODIService -> Repository

apps/studio SPA
  -> /api/chat
  -> stream_chat -> health check
  -> OpenAI-compatible LLM -> MCP tool calls
  -> offline fallback when the LLM is unreachable
```

The SPA sends `mcp_url` with every data request for compatibility. In `local` mode the sidecar ignores it; in `mcp` mode it is required for canvas and mutations.

### Connectors

Connectors are the one path where data enters from outside the local store, and
it has two halves: a durable registry and a volatile ingest buffer.

```text
connectors add [--preset] / connectors catalog
  -> ConnectorRegistry
  -> connectors.json            (shared registry; `${VAR}` placeholders, no secrets)

connectors ingest [--dry-run]
  -> Connector.ingest()         (MCP client or REST call, bounded by a timeout)
  -> IngestBatch                (normalized catalog/resource/tool_result records)
  -> IngestSink                 (in-process, gone when the command exits)
  -> drafts_from_batch -> add_evidence -> Repository   (only when a link id is given)
```

The sink is a hand-off buffer, not storage: nothing survives the process, and
`--dry-run` stops before both the sink append and the evidence writes. Evidence
mapping is the only way connector data reaches the ODI repository, and it goes
through the same `ODIService.add_evidence` path as a hand-entered record.

## Read Paths

```text
ODIService.get_jobs / get_job_map / get_outcomes
  -> Repository read-through state
  -> Pydantic models
  -> JSON (CLI --json, MCP text payload, Studio canvas)
```

Desired outcomes come back ranked by opportunity score (highest first, unscored
last) unless a caller asks for insertion order. The Studio canvas falls back to
the demo seed only in `mcp` mode when MCP is unreachable or returns no jobs. `local` mode returns exactly what is in the local database, including an empty canvas.

## Configuration

| Variable | Used by | Default |
|---|---|---|
| `AGENTIC_ODI_DB` | core SQLite repository | `~/.agentic-odi/odi.db` |
| `AGENTIC_ODI_BACKEND` | CLI, Studio API | `local` |
| `AGENTIC_ODI_MCP_URL` | CLI, Studio defaults | `http://localhost:8000/mcp` |
| `AGENTIC_ODI_CONNECTOR_TIMEOUT` | connector health/ingest calls | `30` seconds |
| `AGENTIC_ODI_STUDIO_DIST` | Studio API, dev launcher | `apps/studio/dist` |
| `AGENTIC_ODI_REPO_ROOT` | Tauri shell | auto-detected |
| `AGENTIC_ODI_BASE_URL` | CLI chat, Studio chat | `http://localhost:8001/v1` |
| `AGENTIC_ODI_MODEL` | CLI chat, Studio chat | `local-tools-model` |
| `AGENTIC_ODI_API_KEY` | CLI chat, Studio chat | `local` |

## Trust Boundaries

- The SPA runs in a browser or Tauri webview and only trusts the sidecar origin.
- The sidecar may reach MCP and the LLM; CORS is restricted to known Studio origins.
- MCP is an HTTP service with no authentication in local development. Do not expose it directly to the internet; the Cloudflare setup tunnels the sidecar, not MCP.
