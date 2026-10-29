# Local-First Storage with Optional Cloudflare D1 Sync

**Date:** 2026-10-20
**Status:** Approved for implementation

## Intent

The product promise is: open Agentic ODI and start working. There is no
database choice, no setup wizard, and no cloud requirement. Data lives on the
user's device by default. When the user wants another device or a teammate,
one action makes the work follow them.

The original request framed Cloudflare D1 as the default database with local
storage as a fallback. The final direction is the reverse: the environment
decides the store. A locally accessed app uses local SQLite. A hosted app uses
D1. A privacy-first user can force local mode even when cloud credentials are
present. D1 is the cloud adapter, not a tax on local users.

## Goals

- Keep zero-setup, offline, local-first behavior as the default.
- Make hosted deployments use Cloudflare D1 without duplicating ODI domain
  logic.
- Let a user opt into sync from a local database to the cloud.
- Support personal workspaces and Better Auth organizations (teams).
- Provide portable export/import as a trust and migration escape hatch.
- Make the enterprise self-hosted tier the same Worker + D1 deployment under
  the customer's own Cloudflare account.
- Keep the existing `ODIService` and MCP contract untouched.

## Non-Goals

- Studio sign-in, workspace switcher, and invitation UI in this slice.
- Hosted chat/LLM deployment and billing.
- Fine-grained field-level conflict resolution (CRDTs).
- Real-time push sync; v1 is explicit push/pull.
- Real Cloudflare deployment in CI.

## UX Principles

1. **No database question.** The user sees "on this device" or "synced", never
   "SQLite or D1".
2. **Local is not a fallback.** It is the privacy promise and the default for
   local access.
3. **Sync is an upgrade, not a migration project.** Signing in should carry
   existing local work along by re-tagging and uploading it, not by asking the
   user to export and re-import.
4. **One escape hatch.** `odi sync export` always produces a complete
   portable bundle; import is idempotent.
5. **Teams are workspaces.** A personal workspace is the user; a team is a
   Better Auth organization.

## Architecture

```text
Local plane (default, no auth, no network)
  SPA / CLI / MCP
    -> ODIService
    -> EventSourcedRepository
    -> IntentStore (SQLite)

Hosted plane (D1)
  Worker + Better Auth
    -> /api/sync/* (event push/pull)
    -> D1 events table
  Hosted sidecar (optional)
    -> D1EventStore (D1 REST API)
    -> ODIService

Bridge
  SyncService (local IntentStore <-> authenticated Worker)
```

The seam is the append-only event log, not the ORM. Local and cloud store the
same event rows. This keeps one domain implementation while allowing two
storage backends.

## Event Contract

Each event has:

| Field | Meaning |
|---|---|
| `id` | Local insertion sequence (SQLite autoincrement) |
| `event_id` | Client-generated UUID, globally unique and idempotent |
| `workspace_id` | Tenant boundary; `local` for unlinked local data |
| `device_id` | Random per-device identifier, never a hostname |
| `timestamp` | ISO-8601 UTC observation time |
| `type` | Existing event types (`JOB_CREATED`, `OUTCOME_UPDATED`, ...) |
| `payload` | Existing JSON payload |
| `server_seq` | D1 `id` once the event has been pushed; `NULL` while pending |

The D1 `events.id` is the canonical server order. Timestamps are not used for
ordering, so clock skew cannot reorder work.

## Sync Protocol

- **Push:** local events with `server_seq IS NULL` are sent in local order. The
  server inserts with `INSERT OR IGNORE` on `event_id`, then returns the
  server sequence for each accepted event in the caller's workspace. Re-push is
  a no-op.
- **Pull:** the client asks for events after its cursor. The server returns
  events in `id` order. The client inserts them idempotently, records the
  cursor, and reloads its snapshot.
- **Conflict rule v1:** last write wins by `server_seq`. Updates are patch
  events; deletes are tombstones. A stale update cannot overwrite a newer
  server-ordered event after a pull reload. This is documented as a v1 limit.
- **Offline:** writes always succeed locally. Sync is explicit and can be
  retried safely.
- **Workspace link:** local data starts as `local`. On first sync the client may
  re-tag it to the authenticated personal or organization workspace. Export
  preserves workspace IDs.

## Storage Selection

`AGENTIC_ODI_STORAGE=auto|local|d1` (default `auto`).

- `auto`: use D1 only when all D1 credentials are present; otherwise SQLite.
- `local`: always SQLite, even when D1 credentials exist.
- `d1`: require D1 configuration and fail loudly if incomplete.

Local access never needs an account. Hosted deployments set `d1` explicitly.

## Auth and Tenancy

- Better Auth on D1 handles users, sessions, and organizations.
- Bearer auth is enabled for CLI/API clients; cookies support the future web UI.
- The authenticated workspace is the session's active organization, or the
  user's own ID for a personal workspace.
- Sync requests may only read/write the authenticated workspace. The Worker
  never trusts a client-supplied workspace beyond that comparison.
- Local mode has no auth and no identity.
- The D1 REST service token is server-side only; it is never given to clients.

## Self-Hosted Enterprise

The same Worker, D1 schema, and Python adapters deploy under a customer's
Cloudflare account. Configuration changes, not code forks:

- `BETTER_AUTH_URL`, `BETTER_AUTH_SECRET`
- D1 binding and database ID
- Optional identity provider (GitHub OAuth today, SSO later)
- Optional custom domain

## Security and Privacy

- Local mode performs no data network calls.
- Sync is opt-in per workspace.
- Batch limits: 500 events, 256 KiB per payload, 5 MiB per request.
- Event IDs, workspace IDs, device IDs, and event types are validated.
- SQL uses prepared statements.
- Cross-workspace event ID collisions are rejected without leaking the other
  workspace's sequence.
- Export bundles contain the user's data in clear JSONL; users control them.

## Failure Handling

- D1 unavailable: hosted reads/writes fail with a clear 5xx; local mode is
  unaffected. Sync retries are safe.
- Partial push: idempotent inserts mean the next push completes the batch.
- Legacy local DB: upgraded in place; event IDs are backfilled uniquely.
- Corrupt remote event: rejected without applying the rest of the batch.

## Verification

- Unit and integration tests must not require Cloudflare credentials.
- Worker tests use Miniflare with a local D1 database.
- The Python D1 client is tested with `httpx.MockTransport`.
- A local -> fake cloud -> fresh local round-trip proves the bridge.
- Full lint, typecheck, bandit, pytest, frontend, and Worker suites pass before
  the PR is opened.
