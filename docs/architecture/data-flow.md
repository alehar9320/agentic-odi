# Data Flow

## Sources of Truth

| Layer | Owns | Persists |
|---|---|---|
| `packages/core` | `Job`, `Step`, `Outcome`, `CustomerOutcome`, `ODIService`, repository protocol | SQLite event log + snapshots |
| `apps/mcp-server` | MCP tool adapters over `ODIService` | `build_repository()` selects SQLite in production and in-memory for `AGENTIC_ODI_DB=:memory:` |
| `apps/studio-api` | Studio API, canvas projection, chat tool loop, conversation history, PM memory | Via the same repository when the local backend is active; conversations and memory in `~/.agentic-odi/studio.db` |
| `packages/connectors` | Connector protocol, presets, record mapping | Shared `connectors.json` registry; ingested batches land in an in-process sink |
| `apps/studio` | Presentation state, the visible conversation path, optimistic canvas updates; the conversation runtime is assistant-ui | Browser cache only |
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
  -> stream_chat -> OpenAI-compatible LLM -> MCP tool calls
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

## The Conversation

One turn is one SSE stream, and the SPA renders it as typed parts rather than a
string. Events, in the order they can appear:

| Event | Payload | Meaning |
|---|---|---|
| `status` | `phase` | `health_check`, `mcp_tools`, `model`, or `offline` |
| `conversation` | `id`, `title` | The thread this turn belongs to |
| `reasoning` | `text` | Model thinking, rendered in a disclosure, never persisted as prose |
| `delta` | `text` | Prose appended to the open text part |
| `tool` | `name`, `status`, `preview` | `start`, `ok`, `error`, or `declined` |
| `approval` | `id`, `tool_call_id`, `name`, `arguments`, `prompt` | A write is waiting for the person |
| `source` | `id`, `title`, `filename`, `mediaType`, `preview` | What the turn actually read |
| `ui` | `id`, `spec` | A validated generated surface |
| `memory`, `connector`, `canvas_dirty` | — | Side effects the SPA applies without a refresh |
| `message` / `error` | `content` / `StudioError` | Exactly one terminal event |

Approval gates are process-local and single-user. `ApprovalRegistry` holds one
`asyncio` future per pending write; `POST /api/approvals/{id}` resolves it and
the same stream continues with the call or with a declined tool result. A
timeout (300 s), a cancelled turn, or sidecar shutdown closes the gate, so a
turn always terminates.

The SPA owns the visible path; the sidecar owns the record. Turns persist with
`message_id` and `parent_id`, and the conversation stores `head_id`:

```text
GET   /api/conversations/latest                -> thread + turns (resume)
GET   /api/conversations/{id}/tree             -> branch tree + head
PATCH /api/conversations/{id} {"head_id"}      -> record the visible branch
```

A conversation written before ids existed has none, so the tree endpoint
synthesises a linear chain and old threads still open. `apps/studio` never
invents a branch the sidecar cannot reproduce.

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
| `AGENTIC_ODI_STUDIO_DB` | Studio API memory | `~/.agentic-odi/studio.db` |
| `AGENTIC_ODI_CONNECTORS_CONFIG` | connectors registry (CLI, Studio, MCP) | `~/.config/agentic-odi/connectors.json` |
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
