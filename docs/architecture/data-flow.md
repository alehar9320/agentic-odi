# Data Flow

## Sources of Truth

| Layer | Owns | Persists |
|---|---|---|
| `packages/core` | `Job`, `Step`, `Outcome`, `CustomerOutcome`, `ODIService`, repository protocol | SQLite event log + snapshots |
| `apps/mcp-server` | MCP tool adapters over `ODIService` | `build_repository()` selects SQLite in production and in-memory for `AGENTIC_ODI_DB=:memory:` |
| `apps/studio-api` | Studio API, canvas projection, chat tool loop, conversation history, PM memory | Via the same repository when the local backend is active; conversations and memory in `~/.agentic-odi/studio.db` |
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
  -> attachments (base64 bytes on the newest user turn) -> image or text part
  -> StudioMemory (conversation turns + remembered observations)

apps/studio SPA (conversation)
  -> ChatMessage[] (the store the sidecar fills)
  -> toThreadMessages -> useExternalStoreRuntime -> ThreadPrimitive.Messages
  -> ActionBar copy / reload (reload -> sendMessage(question, files, {from}))

apps/studio SPA
  -> /api/models
  -> list_models -> OpenAI-compatible /v1/models
  -> {models, message}; an endpoint that will not list is not an error
```

The studio memory is a separate SQLite file, not an ODI repository. It never
feeds the canvas; it only supplies bounded context to the next chat turn.

The SPA sends `mcp_url` with every data request for compatibility. In `local` mode the sidecar ignores it; in `mcp` mode it is required for canvas and mutations.

## Read Paths

```text
ODIService.get_jobs / get_job_map / get_outcomes
  -> Repository read-through state
  -> Pydantic models
  -> JSON (CLI --json, MCP text payload, Studio canvas)
```

The Studio canvas falls back to the demo seed only in `mcp` mode when MCP is unreachable or returns no jobs. `local` mode returns exactly what is in the local database, including an empty canvas.

## Configuration

| Variable | Used by | Default |
|---|---|---|
| `AGENTIC_ODI_DB` | core SQLite repository | `~/.agentic-odi/odi.db` |
| `AGENTIC_ODI_BACKEND` | CLI, Studio API | `local` |
| `AGENTIC_ODI_MCP_URL` | CLI, Studio defaults | `http://localhost:8000/mcp` |
| `AGENTIC_ODI_STUDIO_DB` | Studio API memory | `~/.agentic-odi/studio.db` |
| `AGENTIC_ODI_STUDIO_DIST` | Studio API, dev launcher | `apps/studio/dist` |
| `AGENTIC_ODI_REPO_ROOT` | Tauri shell | auto-detected |
| `AGENTIC_ODI_BASE_URL` | CLI chat, Studio chat | `http://localhost:8001/v1` |
| `AGENTIC_ODI_MODEL` | CLI chat, Studio chat | `local-tools-model` |
| `AGENTIC_ODI_API_KEY` | CLI chat, Studio chat | `local` |

## Trust Boundaries

- The SPA runs in a browser or Tauri webview and only trusts the sidecar origin.
- The sidecar may reach MCP and the LLM; CORS is restricted to known Studio origins.
- MCP is an HTTP service with no authentication in local development. Do not expose it directly to the internet; the Cloudflare setup tunnels the sidecar, not MCP.

## The Failure Path

A failure is a first-class result, not an empty success. The path is the same
for the CLI, the sidecar, and the SPA.

```text
MCP tool result (text)
  -> agentic_odi_core.remote.parse_tool_result
  -> StudioError { code, message, detail, suggestion, retryable, request_id }
  -> sidecar: StudioHTTPError -> HTTP status + {"error": StudioError}
  -> SPA: StudioApiError -> FailurePanel (message, detail, suggestion, Retry)
```

- **One error body.** Every HTTP failure is `{"error": StudioError}`. The SPA
  also reads a legacy `{"detail": "..."}` body, so an older sidecar still
  produces a readable message. Write routes no longer wrap their result in
  `{"ok": true, "result": ...}`: a success is the object, a delete is
  `{"deleted": id}`.
- **One terminal chat event.** Every `/api/chat` stream ends with exactly one
  `message` or one `error`. A recoverable tool error stays a tool result the
  model can read, but it is reported as `status: "error"` and counted. A fatal
  failure ends the stream with `event: error` carrying the `StudioError`.
- **Request ids.** The sidecar accepts or mints `X-Request-ID`, echoes it on
  the response, and puts it on every SSE frame. The MCP server's own log line
  and the `Execution` record (#82) do not carry it yet, and authentication
  (#90) is out of scope.
- **The canvas is a union.** `CanvasState` is `loading | ready | empty |
  error`. An empty canvas is an invitation; a failed canvas is a failure panel
  with Retry. The two never look the same.
- **The thread runtime never owns studio state.** `Conversation` maps the store
  into assistant-ui once per render (`assistant/convert.ts`) and hands it to an
  external-store runtime; run steps, failures, stopped turns, and surfaces ride
  in `metadata.custom` and data parts. A regenerate is a store operation
  (`sendMessage(text, files, {from})`), not a runtime fork, so the transcript
  the sidecar and memory own stays the only transcript.
- **Attachments are bytes, not paths.** A user turn carries `{name, media_type,
  data}` with base64 bytes; an image becomes an `image_url` part and a text file
  becomes a labelled text part. The sidecar re-checks every attachment (valid
  base64, non-empty, 8 MB ceiling, UTF-8 for non-images) and ends the turn with
  one `error` event when one fails, so a filename is never sent as if it were a
  file. Only the newest turn carries files: the SPA strips them from history, and
  the sidecar names them in the remembered turn text instead.
- **The turn log is safe.** One JSON line per turn carries the request id, the
  model, the round and tool counts, the error count, the duration, and the
  outcome. Sensitive keys are dropped rather than redacted, so no token, key,
  or customer quote can reach the log.

