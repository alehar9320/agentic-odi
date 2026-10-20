# Local-First Storage with Optional Cloudflare D1 Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a sync-ready event store seam so local runs stay on SQLite, hosted runs use Cloudflare D1, and users can opt into authenticated sync or portable export/import.

**Architecture:** `ODIService` is unchanged. `IntentStore` grows the sync fields and implements an `EventStore` protocol. `EventSourcedRepository` can sit over SQLite or D1. A new `agentic_odi_cloud` package provides the D1 REST provider, authenticated sync client, and JSONL bundles. A Worker owns D1 and Better Auth; local clients talk only to the sync API.

**Tech Stack:** Python 3.10+, `httpx`, Cloudflare Workers, D1, Better Auth 1.5, TypeScript, Vitest, Miniflare.

**Spec:** `docs/superpowers/specs/2026-10-20-storage-provider-sync-design.md`

## Global Constraints

- Python >= 3.10.
- `packages/core` must continue to depend on no other workspace package.
- Local mode must make zero data network calls.
- `AGENTIC_ODI_STORAGE=local` always wins over D1 credentials.
- Default local database remains `~/.agentic-odi/odi.db`.
- Tests run without Cloudflare credentials or network.
- No secrets in source; `.dev.vars` is ignored.
- Keep README/docs current in the same change.

## Review Focus

1. Malformed or hostile sync payloads must not corrupt local data or leak
   another workspace's server sequence.
2. Concurrent edits from two devices must converge to server order; deletes
   must not be resurrected.
3. Legacy databases must upgrade in place with unique event IDs and no loss.
4. Local mode with D1 credentials present must still make no data network calls.
5. Clock skew must not affect ordering; server sequence is authoritative.

---

### Task 1: Core event contract and SQLite migration

**Files:**
- Create: `packages/core/src/agentic_odi_core/events.py`
- Modify: `packages/core/src/agentic_odi_core/intent_store.py`
- Test: `packages/core/tests/test_events.py`
- Test: `packages/core/tests/test_intent_store.py`

**Interfaces:**
- Produces: `Event`, `EventStore`, `DEFAULT_WORKSPACE`, `DEFAULT_DEVICE`,
  `new_event_id()`, `resolve_device_id(path: Path | None = None) -> str`.
- Produces: `IntentStore.append(...) -> Event`, `get_stream(...) -> list[Event]`,
  `insert_remote(events) -> int`, `mark_synced(mapping) -> int`,
  `retag_workspace(old, new) -> int`, `max_server_seq(workspace_id) -> int`,
  `get_cursor(workspace_id) -> int`, `set_cursor(workspace_id, url, seq)`,
  `pending_count(workspace_id) -> int`, `clear(workspace_id=None)`.

- [ ] **Step 1: Write failing tests**

```python
def test_legacy_db_backfills_unique_event_ids(tmp_path):
    db = tmp_path / "odi.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE events (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL, event_type TEXT NOT NULL, payload TEXT NOT NULL)")
    conn.execute("INSERT INTO events (timestamp, event_type, payload) VALUES ('2026-01-01T00:00:00', 'JOB_CREATED', '{\"id\": \"j1\"}')")
    conn.commit(); conn.close()

    store = IntentStore(str(db))
    events = store.get_stream()
    assert len(events) == 1
    assert events[0]["event_id"]
    assert events[0]["workspace_id"] == "local"
    assert events[0]["device_id"] == "local"
    assert events[0]["server_seq"] is None
```

```python
def test_append_returns_event_and_duplicate_event_id_is_idempotent(tmp_path):
    store = IntentStore(str(tmp_path / "e.db"))
    first = store.append("JOB_CREATED", {"id": "j1"}, event_id="evt-1")
    second = store.append("JOB_CREATED", {"id": "j1"}, event_id="evt-1")
    assert first["event_id"] == second["event_id"]
    assert len(store.get_stream()) == 1
```

```python
def test_workspace_filter_and_pending_counts(tmp_path):
    store = IntentStore(str(tmp_path / "e.db"))
    store.append("JOB_CREATED", {"id": "a"}, workspace_id="ws-a")
    store.append("JOB_CREATED", {"id": "b"}, workspace_id="ws-b")
    assert [e["payload"]["id"] for e in store.get_stream(workspace_id="ws-a")] == ["a"]
    assert store.pending_count("ws-a") == 1
    store.mark_synced({store.get_stream(workspace_id="ws-a")[0]["event_id"]: 7})
    assert store.pending_count("ws-a") == 0
    assert store.get_cursor("ws-a") == 7
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/core/tests/test_events.py packages/core/tests/test_intent_store.py -q`
Expected: FAIL for missing fields/methods.

- [ ] **Step 3: Implement the event contract and migration**

Use `uuid.uuid4().hex` for `event_id`. Use `datetime.now(timezone.utc).isoformat()`
for timestamps. Migration adds columns when absent:

```sql
ALTER TABLE events ADD COLUMN event_id TEXT;
ALTER TABLE events ADD COLUMN workspace_id TEXT NOT NULL DEFAULT 'local';
ALTER TABLE events ADD COLUMN device_id TEXT NOT NULL DEFAULT 'local';
ALTER TABLE events ADD COLUMN server_seq INTEGER;
UPDATE events SET event_id = lower(hex(randomblob(16))) WHERE event_id IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS events_event_id ON events(event_id);
CREATE INDEX IF NOT EXISTS events_workspace_server ON events(workspace_id, server_seq);
CREATE TABLE IF NOT EXISTS sync_state (
  workspace_id TEXT PRIMARY KEY,
  remote_url TEXT NOT NULL DEFAULT '',
  last_server_seq INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL
);
```

`get_stream(replay_order=True)` orders rows with `server_seq` first by
`server_seq`, then pending rows by local `id`. `insert_remote` uses
`INSERT OR IGNORE` and sets `server_seq`. `retag_workspace` updates rows and
`sync_state`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/core/tests/test_events.py packages/core/tests/test_intent_store.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/agentic_odi_core/events.py packages/core/src/agentic_odi_core/intent_store.py packages/core/tests/test_events.py packages/core/tests/test_intent_store.py
git commit -m "feat(core): add sync-ready event store schema"
```

---

### Task 2: Workspace-scoped repository and factory

**Files:**
- Modify: `packages/core/src/agentic_odi_core/sqlite_repository.py`
- Modify: `packages/core/src/agentic_odi_core/factory.py`
- Modify: `packages/core/src/agentic_odi_core/__init__.py`
- Test: `packages/core/tests/test_sqlite_repository.py`
- Test: `packages/core/tests/test_repository_factory.py`

**Interfaces:**
- Produces: `EventSourcedRepository(db_path=None, workspace_id=None, store=None, device_id=None)`.
- Keeps: `SQLiteRepository = EventSourcedRepository` compatibility alias.
- Produces: `EventSourcedRepository.reload() -> None`.
- Produces: `build_repository(db_path=None, workspace_id=None, device_id=None) -> Repository`.

- [ ] **Step 1: Write failing tests**

```python
def test_repositories_are_workspace_isolated(tmp_path):
    db = str(tmp_path / "odi.db")
    a = EventSourcedRepository(db_path=db, workspace_id="ws-a")
    b = EventSourcedRepository(db_path=db, workspace_id="ws-b")
    a.add_job(Job(id="a", name="A"))
    b.add_job(Job(id="b", name="B"))
    assert [j.id for j in a.list_jobs()] == ["a"]
    assert [j.id for j in b.list_jobs()] == ["b"]
```

```python
def test_factory_reads_workspace_and_device(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTIC_ODI_DB", str(tmp_path / "odi.db"))
    monkeypatch.setenv("AGENTIC_ODI_WORKSPACE", "ws-env")
    repo = build_repository()
    assert repo.workspace_id == "ws-env"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/core/tests/test_sqlite_repository.py packages/core/tests/test_repository_factory.py -q`
Expected: FAIL for missing constructor arguments/behavior.

- [ ] **Step 3: Implement workspace scoping**

All `store.append` calls pass `workspace_id` and `device_id`. `_load_snapshot`
uses `replay_order=True`. `reload()` calls `_load_snapshot()`. Add
`workspace_id` and `device_id` attributes. Factory resolves env in this order:
explicit argument, `AGENTIC_ODI_WORKSPACE`, `local`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/core/tests -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/core
git commit -m "feat(core): scope repositories to a workspace"
```

---

### Task 3: Cloud package and D1 provider

**Files:**
- Create: `packages/cloud/pyproject.toml`
- Create: `packages/cloud/src/agentic_odi_cloud/__init__.py`
- Create: `packages/cloud/src/agentic_odi_cloud/d1.py`
- Create: `packages/cloud/src/agentic_odi_cloud/factory.py`
- Modify: `pyproject.toml` (workspace members, coverage)
- Test: `packages/cloud/tests/test_d1_client.py`
- Test: `packages/cloud/tests/test_d1_store.py`
- Test: `packages/cloud/tests/test_factory.py`

**Interfaces:**
- Produces: `D1Config.from_env() -> D1Config | None`.
- Produces: `D1Client(config, client=None)` with `query`, `execute`, `batch`.
- Produces: `D1EventStore(client, workspace_id, device_id)` implementing `EventStore`.
- Produces: `build_d1_repository(workspace_id=None) -> EventSourcedRepository`.
- Produces: `build_repository_from_env() -> Repository`.
- Produces: `storage_provider() -> str` (`local` or `d1`).

- [ ] **Step 1: Write failing tests**

```python
def test_d1_client_posts_query_to_rest_api():
    seen = {}
    def handler(request):
        seen["url"] = str(request.url)
        seen["json"] = json.loads(request.content)
        return httpx.Response(200, json={"success": True, "result": [{"results": [{"id": 1}]}]})
    config = D1Config(account_id="acct", database_id="db", api_token="token")
    client = D1Client(config, client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert client.query("SELECT 1", ()) == [{"id": 1}]
    assert seen["url"].endswith("/accounts/acct/d1/database/db/query")
    assert seen["json"]["sql"] == "SELECT 1"
```

```python
def test_forced_local_wins_over_d1_env(monkeypatch):
    monkeypatch.setenv("AGENTIC_ODI_STORAGE", "local")
    monkeypatch.setenv("AGENTIC_ODI_D1_ACCOUNT_ID", "a")
    monkeypatch.setenv("AGENTIC_ODI_D1_DATABASE_ID", "d")
    monkeypatch.setenv("AGENTIC_ODI_D1_API_TOKEN", "t")
    monkeypatch.setenv("AGENTIC_ODI_DB", ":memory:")
    assert isinstance(build_repository_from_env(), InMemoryRepository)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/cloud/tests -q`
Expected: collection errors for missing package.

- [ ] **Step 3: Implement D1 client and store**

Use the REST endpoint
`/client/v4/accounts/{account_id}/d1/database/{database_id}/query`.
Raise `D1Error` on `success=false` or non-2xx. `execute` returns
`meta.last_row_id` when present. `batch` posts `{"batch": [...]}`.
`D1EventStore` mirrors the `IntentStore` SQL. `get_cursor` returns
`max(server_seq)`. `set_cursor` is a no-op for a direct D1 store.
`build_repository_from_env` uses `auto|local|d1` as specified.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/cloud/tests -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/cloud pyproject.toml uv.lock
git commit -m "feat(cloud): add Cloudflare D1 event store provider"
```

---

### Task 4: Sync service and portable bundles

**Files:**
- Create: `packages/cloud/src/agentic_odi_cloud/sync.py`
- Create: `packages/cloud/src/agentic_odi_cloud/bundle.py`
- Test: `packages/cloud/tests/test_sync.py`
- Test: `packages/cloud/tests/test_bundle.py`

**Interfaces:**
- Produces: `SyncTransport` protocol: `push(workspace_id, events)`, `pull(workspace_id, after, limit)`.
- Produces: `HttpSyncTransport(base_url, token, timeout=30.0)`.
- Produces: `SyncService(store, transport, workspace_id)` with `link_workspace`,
  `push`, `pull`, `sync`, `status`.
- Produces: `export_bundle(store, workspace_id, path)`, `import_bundle(store, path)`.

- [ ] **Step 1: Write failing tests**

```python
def test_push_marks_events_synced_and_is_idempotent(tmp_path):
    store = IntentStore(str(tmp_path / "e.db"))
    store.append("JOB_CREATED", {"id": "j1"})
    transport = FakeTransport(server_seqs={store.get_stream()[0]["event_id"]: 11})
    sync = SyncService(store, transport, "local")
    assert sync.push() == 1
    assert store.pending_count("local") == 0
    assert sync.push() == 0
```

```python
def test_pull_reloads_in_server_order(tmp_path):
    store = IntentStore(str(tmp_path / "e.db"))
    local_evt = store.append("JOB_CREATED", {"id": "mine"})
    remote = {"event_id": "remote-1", "workspace_id": "local", "device_id": "d2",
              "timestamp": "2026-01-01T00:00:00+00:00", "type": "JOB_CREATED",
              "payload": {"id": "theirs"}, "server_seq": 1}
    transport = FakeTransport(pull_events=[remote])
    sync = SyncService(store, transport, "local")
    assert sync.pull() == 1
    assert store.get_cursor("local") == 1
```

```python
def test_export_import_round_trip_preserves_entities(tmp_path):
    source = EventSourcedRepository(db_path=str(tmp_path / "a.db"))
    source.add_job(Job(id="j1", name="Onboard"))
    bundle = export_bundle(source.store, "local", tmp_path / "bundle.jsonl")
    target = EventSourcedRepository(db_path=str(tmp_path / "b.db"))
    import_bundle(target.store, bundle)
    assert target.get_job("j1").name == "Onboard"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/cloud/tests/test_sync.py packages/cloud/tests/test_bundle.py -q`
Expected: FAIL for missing modules.

- [ ] **Step 3: Implement sync and bundles**

`push` sends pending events; maps returned `event_id -> server_seq`; calls
`mark_synced`; reloads. `pull` calls the transport with the stored cursor;
inserts remotely; sets the cursor; reloads. `sync` pushes then pulls.
`HttpSyncTransport` uses `Authorization: Bearer <token>` and the JSON shapes in
the spec. Bundle format is a header line
`{"format": "odi-events/v1", "workspace_id": "..."}` followed by one event
JSON per line. Import validates the header and uses `insert_remote` semantics
while preserving event IDs.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/cloud/tests -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/cloud
git commit -m "feat(cloud): add authenticated sync and portable bundles"
```

---

### Task 5: CLI sync commands

**Files:**
- Create: `apps/cli/src/agentic_odi_cli/sync.py`
- Modify: `apps/cli/src/agentic_odi_cli/cli.py`
- Modify: `apps/cli/pyproject.toml`
- Test: `apps/cli/tests/test_sync_cli.py`

**Interfaces:**
- Consumes: `SyncService`, `HttpSyncTransport`, `export_bundle`, `import_bundle`.
- Produces: `odi sync status|push|pull|export|import`.
- Env: `AGENTIC_ODI_SYNC_URL`, `AGENTIC_ODI_SYNC_TOKEN`, `AGENTIC_ODI_WORKSPACE`.

- [ ] **Step 1: Write failing tests**

```python
def test_sync_status_reports_local_provider(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTIC_ODI_DB", str(tmp_path / "odi.db"))
    monkeypatch.delenv("AGENTIC_ODI_SYNC_URL", raising=False)
    result = CliRunner().invoke(app, ["sync", "status"])
    assert result.exit_code == 0
    assert "sqlite" in result.output.lower()

def test_sync_push_requires_url_and_token(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTIC_ODI_DB", str(tmp_path / "odi.db"))
    monkeypatch.delenv("AGENTIC_ODI_SYNC_URL", raising=False)
    result = CliRunner().invoke(app, ["sync", "push"])
    assert result.exit_code != 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest apps/cli/tests/test_sync_cli.py -q`
Expected: FAIL for missing command.

- [ ] **Step 3: Implement commands**

Use a Typer sub-app. `push` and `pull` require URL and token and exit 2 with a
clear message when missing. `export`/`import` work offline. `status` prints
provider, workspace, pending count, and whether a remote is configured. Never
print the token.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest apps/cli/tests -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/cli
git commit -m "feat(cli): add sync and portable export commands"
```

---

### Task 6: Cloudflare Worker, D1 schema, Better Auth

**Files:**
- Create: `infra/cloudflare/src/{worker,auth,identity,sync,events,env}.ts`
- Create: `infra/cloudflare/migrations/0001_events.sql`
- Create: `infra/cloudflare/migrations/0002_auth.sql`
- Create: `infra/cloudflare/{package.json,package-lock.json,tsconfig.json,vitest.config.ts,.dev.vars.example}`
- Create: `infra/cloudflare/test/{sync,events,schema}.test.ts`
- Modify: `wrangler.jsonc`
- Modify: `.gitignore`
- Modify: `.github/workflows/ci.yml`

**Interfaces:**
- Produces: `POST /api/sync/push`, `GET /api/sync/pull`, `GET /api/sync/status`.
- Produces: `ALL /api/auth/*`.
- Produces: D1 `events` table with `id`, `event_id`, `workspace_id`,
  `device_id`, `timestamp`, `event_type`, `payload`, `created_at`.
- Produces: `createAuth(env)`, `resolveIdentity(auth, request)`,
  `handlePush(db, identity, body)`, `handlePull(db, identity, query)`.

- [ ] **Step 1: Write failing tests**

```ts
it("rejects unauthenticated sync", async () => {
  const res = await worker.fetch(new Request("https://example.com/api/sync/push", { method: "POST" }), env);
  expect(res.status).toBe(401);
});

it("push is idempotent", async () => {
  const body = { events: [event("evt-1")] };
  const first = await handlePush(env.DB, identity, body);
  const second = await handlePush(env.DB, identity, body);
  expect(first.server_seqs["evt-1"]).toBe(second.server_seqs["evt-1"]);
});

it("cannot write another workspace", async () => {
  await expect(handlePush(env.DB, identity, { events: [event("evt-1", "other")] }))
    .rejects.toMatchObject({ status: 403 });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm --prefix infra/cloudflare test`
Expected: FAIL for missing files.

- [ ] **Step 3: Implement Worker and auth**

Worker routing: `/api/auth/*` to Better Auth, `/api/sync/*` to sync handlers,
other `/api/*` to `SIDECAR_URL` as today, everything else to `ASSETS`.
Better Auth config: native `database: env.DB`, `organization()`, `bearer()`,
`magicLink()` with a `sendMagicLink` that logs in development and uses Resend
when `RESEND_API_KEY` is set. `resolveIdentity` uses
`auth.api.getSession({ headers })` and returns
`{ userId, workspaceId: session.session.activeOrganizationId ?? session.user.id }`.
Validate `workspace_id` equality, event IDs, types, payload size, batch size.
Use prepared statements and `env.DB.batch()`. Add D1 migrations and a
test-only wrangler config. Add the Worker job to CI.

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm --prefix infra/cloudflare test && npm --prefix infra/cloudflare run typecheck`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add infra/cloudflare wrangler.jsonc .gitignore .github/workflows/ci.yml
git commit -m "feat(cloudflare): add D1 sync API and Better Auth"
```

---

### Task 7: App wiring and storage status

**Files:**
- Modify: `apps/studio-api/src/agentic_odi_studio_api/app.py`
- Modify: `apps/studio-api/pyproject.toml`
- Modify: `apps/mcp-server/src/agentic_odi_mcp_server/mcp_server.py`
- Modify: `apps/mcp-server/pyproject.toml`
- Test: `apps/studio-api/tests/test_storage_status.py`
- Test: `apps/mcp-server/tests/test_repository_selection.py`

**Interfaces:**
- Consumes: `build_repository_from_env()`, `storage_provider()`.
- Produces: `GET /api/storage` returning provider, workspace, pending count,
  cursor, and sync-configured flag. No credentials.

- [ ] **Step 1: Write failing tests**

```python
def test_studio_defaults_to_local(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTIC_ODI_DB", str(tmp_path / "odi.db"))
    monkeypatch.delenv("AGENTIC_ODI_STORAGE", raising=False)
    app = create_app()
    client = TestClient(app)
    body = client.get("/api/storage").json()
    assert body["provider"] == "local"
    assert "token" not in json.dumps(body).lower()

def test_forced_local_beats_d1_env(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTIC_ODI_DB", str(tmp_path / "odi.db"))
    monkeypatch.setenv("AGENTIC_ODI_STORAGE", "local")
    monkeypatch.setenv("AGENTIC_ODI_D1_ACCOUNT_ID", "a")
    monkeypatch.setenv("AGENTIC_ODI_D1_DATABASE_ID", "d")
    monkeypatch.setenv("AGENTIC_ODI_D1_API_TOKEN", "t")
    app = create_app()
    assert TestClient(app).get("/api/storage").json()["provider"] == "local"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest apps/studio-api/tests/test_storage_status.py -q`
Expected: FAIL for missing route.

- [ ] **Step 3: Implement provider selection**

Replace direct `SQLiteRepository()` construction with
`build_repository_from_env()`. Add the status route. For D1, wrap canvas and
mutation calls in `run_in_threadpool` so network I/O does not block the event
loop. Keep the MCP server behavior identical for memory tests.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest apps/studio-api/tests apps/mcp-server/tests -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/studio-api apps/mcp-server
git commit -m "feat(apps): select storage provider from the environment"
```

---

### Task 8: Documentation, full verification, PR

**Files:**
- Create: `docs/architecture/storage-and-sync.md`
- Modify: `docs/architecture/README.md`
- Modify: `docs/architecture/data-flow.md`
- Modify: `docs/deployment.md`
- Modify: `docs/cli.md`
- Modify: `docs/roadmap.md`
- Modify: `docs/development.md`
- Modify: `README.md`

- [ ] **Step 1: Write docs**

Document the two planes, storage selection, event schema, sync protocol,
conflict rule, auth, export/import, self-hosted setup, D1 migrations, Worker
secrets, and all new env vars. Add `packages/cloud` to the code overview and
sync commands to the CLI guide.

- [ ] **Step 2: Run the full verification suite**

```bash
uv sync --all-packages --locked
uv run ruff check .
uv run ruff format --check .
uv run mypy apps packages
uv run bandit -c pyproject.toml -r apps packages
uv run pytest
npm --prefix apps/studio run lint
npm --prefix apps/studio run typecheck
npm --prefix apps/studio test -- --run
npm --prefix infra/cloudflare ci
npm --prefix infra/cloudflare test
npm --prefix infra/cloudflare run typecheck
```

Expected: all pass.

- [ ] **Step 3: Run the end-to-end round-trip**

```bash
uv run python - <<'PY'
# create local repo, add a job, export, import into a fresh DB, assert
PY
```

Expected: imported job matches.

- [ ] **Step 4: Commit docs**

```bash
git add docs README.md
git commit -m "docs: document local-first storage and D1 sync"
```

- [ ] **Step 5: Push and open the stacked PR**

```bash
git push -u origin feature/storage-provider-sync
gh pr create --base topic/repository-structure --head feature/storage-provider-sync \
  --title "feat(storage): local-first event store with Cloudflare D1 sync" \
  --body "Implements the approved design. Verification: full pytest, ruff, mypy, bandit, studio, and worker suites."
```

Expected: PR URL printed; report it.
