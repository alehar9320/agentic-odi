# Trust boundaries

Agentic ODI runs as several processes on one machine (and, optionally, one
proxied process in the cloud). This document says what each one may reach, where
the credentials are, and what crosses each wire — including the places where the
boundary is deliberately absent.

## The processes

| Process | Runs where | Can reach |
|---|---|---|
| **CLI** (`agentic_odi_cli`) | terminal | local SQLite (`~/.agentic-odi/odi.db`), the user's config directory, MCP over HTTP, the LLM endpoint |
| **MCP server** (`agentic_odi_mcp_server`) | `:8000/mcp` | the same SQLite store; no outbound LLM calls |
| **Studio API** (`agentic_odi_studio_api`) | `127.0.0.1:8100` | the ODI store, `~/.agentic-odi/studio.db` for conversation and PM memory, MCP, the LLM, connector endpoints |
| **Studio SPA** | browser or Tauri webview | only the sidecar origin; browser storage for settings and session context |
| **Cloudflare Worker** | edge | `SIDECAR_URL` and static assets |
| **Tauri shell** | desktop | spawns the sidecar, reads the local filesystem, contacts the release endpoint for updates |

The dependency direction is enforced in code: the SPA never talks to MCP or the
LLM directly; the sidecar is its only backend.

## Credentials

- **LLM key.** Resolution order is `AGENTIC_ODI_API_KEY`, then `api_key` in the
  plaintext profile at `~/.config/agentic-odi/llm_profile.json`, then the
  literal `local` for self-hosted models (`apps/cli/src/agentic_odi_cli/chat.py:90-94`).
  The sidecar resolves the same values and **returns the resolved key** from
  `GET /api/config` (`studio/probes.py:37-49`) so the browser can display and
  edit it. The key is stored in the SPA's `localStorage` alongside the rest of
  the Studio settings.
- **Connector tokens.** A connector config names the environment variables it
  needs and expands `${VAR}` at call time
  (`packages/connectors/src/agentic_odi_connectors/models.py:56-64`,
  `mcp/connector.py:78-89`). The app stores names, not values.
- **OAuth tokens.** FastMCP's client cache is in memory for the life of one CLI
  process, so an OAuth connector may ask for consent again on the next command.
- **The per-install sidecar token.** 32 random URL-safe bytes at
  `~/.config/agentic-odi/studio-token` (override with
  `AGENTIC_ODI_STUDIO_TOKEN`, which names the file, not the value), issued
  lazily by whichever local process starts first and reused by the rest
  (`apps/studio-api/src/agentic_odi_studio_api/studio/paths.py`). It is a
  shared local secret, not an identity: every holder of the file has the same
  rights.
- **MCP URL.** A request argument or `AGENTIC_ODI_MCP_URL`; not a secret.

## What crosses each wire

- **SPA → sidecar:** JSON over HTTP and server-sent events on `/api/*`. The SPA
  attaches the sidecar token from the `studio.token` key in `localStorage`
  (`apps/studio/src/api/studioApi.ts`); how that key gets into a real browser is
  still open — see "What this does not do". The one exception to "no secrets in
  the browser" is the LLM key described above.
- **Sidecar → MCP:** JSON-RPC tool calls, carrying the same token.
- **Sidecar → LLM:** OpenAI-compatible HTTP chat completions.
- **Worker → sidecar:** the worker forwards `/api/*`, including the client's
  `Authorization` header, to `SIDECAR_URL` (`infra/cloudflare/worker.ts:190-232`).
  It does not authenticate the client itself.
- **Tauri → GitHub releases:** fetches `latest.json`, verifies the artifact
  signature against the key pinned in `tauri.conf.json`, and stages an update
  only after verification.

## Controls that exist

- **Loopback binding.** The sidecar listens on `127.0.0.1:8100`. FastMCP's HTTP
  server defaults to loopback as well. Neither is meant to be exposed directly.
- **Per-install bearer token.** Every `/api` route on the sidecar and the MCP
  HTTP endpoint answer `401` unless the request carries
  `Authorization: Bearer <token>` with the issued key. `/health` and the static
  shell stay open, because the deployment's readiness probe and the browser's
  first request need them. The comparison is constant-time, and the token is
  never read from a URL or a query string.
- **CORS allow-list.** The sidecar accepts `tauri://localhost`,
  `localhost:5173`, `127.0.0.1:5173`, `localhost:8100`, and `127.0.0.1:8100`,
  without credentials (`app.py:38-45`, `:211-213`).
- **Hosted topology.** The Cloudflare setup tunnels the sidecar, not MCP; the
  MCP port stays local.
- **Signed updates.** The desktop updater verifies signatures before staging.
- **Prompt-level consent.** Conversational writes pause for an approval card; see
  [Consent and approvals](consent.md).

## What the alternatives were

- **No token at all.** The position this document held until
  [#575](https://github.com/alehar9320/agentic-odi/issues/575): the sidecar
  serves one person on loopback, so the setup cost lands on every local run for
  little gain. It stops being true the moment the sidecar is reachable
  off-host, which the Cloudflare tunnel already does.
- **Keep the LLM key server-side.** The SPA only needs to display and change it;
  the sidecar could own the value and never return it. This is the gap
  [#90](https://github.com/alehar9320/agentic-odi/issues/90) tracks.
- **Worker-side authentication.** The worker forwards headers rather than
  terminating auth, so the hosted path is only as protected as the sidecar.

## What this does not do

- It does not say *who* holds the sidecar token. Any process that can read the
  profile directory has the same rights as the Studio.
- It does not yet put the key where every client can find one. The browser
  reads `studio.token` from `localStorage` and nothing in the shipped app
  writes it, so a launcher or the desktop shell must seed it; the CLI's own MCP
  clients (`apps/cli/src/agentic_odi_cli/backend.py`, `chat.py`) connect
  without the header and are refused by a gated server.
- It does not encrypt data at rest. The SQLite databases and the LLM profile are
  plaintext files in the user's home directory.
- It does not sandbox connector code or the LLM's network egress beyond the
  endpoints the config names.
- It does not keep the LLM key out of the browser, and it does not persist
  approval decisions.
- It is not a multi-tenant boundary: one running sidecar serves one person.
