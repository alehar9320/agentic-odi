# Design: SQLite is the only copy: verify, checkpoint, back up (#348)

**Source issue:** https://github.com/alehar9320/agentic-odi/issues/348  
**Date:** 2026-10-31  
**Status:** groomed, ready to implement (amended 2026-10-31 — see below)  
**Labels carried over:** `spec`, `opportunity`, `priority/high`, `area/core`, `area/infra`, `theme/engineering`

---

## 1. Value score: 5 / 5

Data durability. The ODI repository is one SQLite file with no integrity check, no checkpoint policy, no backup, and no restore path; the sidecar never closes it on exit. If the file is damaged, the app dies on boot with a traceback and the work is gone. After this issue, the app detects corruption at boot, checkpoints on a schedule, takes rotating backups with SQLite's own backup API, and offers a tested restore command.

**One value increment:** The app opens, notices a damaged database, and says which file is damaged and where the last good copy is. A restore command puts it back, prints counts before and after, and the canvas returns — no traceback, no lost work.

---

## 2. Preconditions / external dependencies

None within this batch. Adjacent to #118 (`odi data export`, JSON portability — not a durability path; cannot restore a corrupt file) and extends #122 (closed, committed pending transactions on MCP shutdown — this adds the checkpoint, backup, and close that shutdown still lacks).

## 2026-10-31 spec amendments (binding)

- Confirm whether #130's graceful shutdown already closes the DB; strike the claim if so (avoid duplicating close logic).
- Define the integrity-check policy with a boot time budget (`quick_check` at boot; full check scheduled).
- Verify the checkpoint policy does not break the existing "no `-wal`/`-shm` remains" test (`test_sqlite_repository.py:473-483`).
- Mandate the online backup API (`sqlite3.Connection.backup()`), never a file copy; add a test that a backup restores to an identical database.
- Make restore dry-runnable and refuse to overwrite a live DB without an explicit flag.

---

## 3. Atomic implementation steps

### Step 1 — Boot integrity gate in `SQLiteRepository.__init__`

In `packages/core/src/agentic_odi_core/sqlite_repository.py`, before `_load_snapshot` (`:43`):
- Run `PRAGMA quick_check` (cheap relative to the full replay the constructor already performs at `:46-55`).
- On a non-`ok` result, run `PRAGMA integrity_check`, keep up to 20 rows of output, and raise `StoreCorrupt(StoreError)` from `agentic_odi_core.errors`, carrying the path and the rows.
- Never delete, rewrite, or silently substitute an empty database. A corrupt store must fail reads, not answer them with nothing.

`apps/studio-api/src/agentic_odi_studio_api/main.py` catches `StoreCorrupt`, prints one line naming the file, the error count, and the restore command, and exits non-zero. The same exception reaches the CLI as a normal error body rather than a traceback.

`StudioMemory` gets the same gate on open (`studio/memory.py:240-253`), with a distinct message: memory loss is recoverable, the canvas is not.

**Test:** opening a truncated database raises `StoreCorrupt` with the file named; the sidecar exits with one actionable line, not a traceback; a healthy database opens with no behaviour change and no new warning output.

**Definition of done:** `quick_check` at boot; `StoreCorrupt` raised with path + rows; sidecar exits non-zero with actionable line; `StudioMemory` gated too.

---

### Step 2 — Checkpoint policy

- `PRAGMA wal_checkpoint(TRUNCATE)` immediately after the boot integrity check, and in `IntentStore.close()` before `conn.close()` (`intent_store.py:294-300`), guarded by the existing 5000 ms `busy_timeout`.
- `PRAGMA wal_checkpoint(PASSIVE)` after `IntentStore.clear()` (`:276-283`), because a bulk delete leaves a large log behind.
- Expose `journal_mode`, `wal_size_bytes`, and the last checkpoint time through the diagnostics route proposed in #351 so the policy can be observed.

**Test:** after a write and a clean shutdown, no `-wal` or `-shm` remains; the checkpoint policy does not break the existing no-sidecar test.

**Definition of done:** TRUNCATE checkpoint after boot check and on close; PASSIVE after clear; diagnostics expose journal/WAL/checkpoint state.

---

### Step 3 — Backups with SQLite's online backup API

- Engine: `sqlite3.Connection.backup()` from the same connection — **never `shutil.copy2`** (copying a live SQLite DB misses pages committed only to `-wal`). The stdlib online backup produces a consistent snapshot even while another process holds the database.
- Location: `~/.agentic-odi/backups/`, files `odi-<UTC>.db` and `studio-<UTC>.db`, matching the `.bak-<UTC>` convention in `apps/cli/src/agentic_odi_cli/profile.py:121`.
- Write to `<name>.tmp`, open the copy read-only and `quick_check` it, then `os.replace` into place — the same temp-then-replace discipline as `profile.py:103-107`.
- Triggers, all cheap: after a successful boot check when the newest backup is older than 24 hours; on clean shutdown when the newest is older than 6 hours; and on demand from `agentic-odi doctor --backup`.
- Retention: keep the newest 7 files per database; delete older ones. No other cadence encoded.
- A failed backup never blocks a turn: log one line and record `backup.last_error` for the diagnostics bundle.

**Test:** after a write and clean shutdown, the newest backup passes `quick_check`; backups rotate to 7 per database; a failed backup never blocks a turn; `doctor --backup` triggers a backup on demand.

**Definition of done:** Online backup API used (never file copy); temp-then-replace; rotation to 7; on-demand backup via `doctor --backup`; failed backups non-fatal.

---

### Step 4 — Restore command

`agentic-odi restore --from <file> [--yes]`:
1. Open the backup read-only and `quick_check` it; refuse on failure.
2. Refuse if the live database is in use: open a connection and attempt `BEGIN IMMEDIATE`; a lock means another process owns it.
3. Refuse if the backup's schema is newer than this binary (`PRAGMA user_version`).
4. Move the live file and any `-wal`/`-shm` to `<name>.pre-restore-<UTC>`.
5. Copy the backup into place, re-run the boot check, print counts before and after.

Without `--yes`, print what would change and exit 0 (dry run).

Set `PRAGMA user_version` in `IntentStore._init_db` (`intent_store.py:40-75`) and in `_migrate` (`studio/memory.py:181-190`), so step 3 is possible at all. Neither store records a version today.

**Test:** `restore` refuses a corrupt backup, a locked database, and a newer schema; a valid backup restores with identical counts; dry run prints changes and exits 0.

**Definition of done:** `restore` refuses corrupt/locked/newer-schema; valid backup restores with identical counts; dry-run supported; `PRAGMA user_version` set in both stores.

---

### Step 5 — `doctor` durability report

`agentic-odi doctor` reports, for both databases: path basename, `quick_check` result, WAL size, entity counts, schema version, and the newest backup.

**Test:** `doctor` output includes all fields for both DBs; after a corrupt file, `doctor` fails; after restore, `doctor` passes and counts match.

**Definition of done:** `doctor` reports durability state for both databases.

---

### Step 6 — Migration fixtures

Commit real databases under `packages/core/tests/fixtures/db/`:
- one from the pre-`event_id` schema
- one with `event_id` but no `workspace_id`
- one with a NULL `event_id`
Generate them with a checked-in script and keep them small.

Tests open each fixture through `SQLiteRepository` and assert every entity reads back and ids were backfilled exactly once. A second fixture set for `StudioMemory` covers `_MIGRATIONS` (`memory.py:174-178`), today exercised only against a freshly created schema. A forward-version fixture (`user_version` above the binary) must be refused with a clear message, not half-read.

**Test:** every migration fixture reads back all entities; the forward-version fixture is refused.

**Definition of done:** Real migration fixtures committed; fixtures read back correctly; forward-version refused.

---

### Step 7 — Shutdown: try/finally close both stores

The lifespan becomes `try/finally`: cancel approvals, checkpoint, take the shutdown backup, close the repository, close memory. Closing is idempotent (`intent_store.py:294-298`), so tests that already close stay valid.

Confirm whether #130's graceful shutdown already closes the DB; if so, coordinate rather than duplicate.

**Test:** a test asserts `close()` was called on both stores during lifespan shutdown.

**Definition of done:** Lifespan closes both stores in `try/finally`; close is idempotent; test asserts close called.

---

## 4. Non-negotiable constraints

- Opening a truncated database raises `StoreCorrupt` with the file named; the sidecar exits with one actionable line, not a traceback.
- A healthy database opens with no behaviour change and no new warning output.
- Backups rotate to 7 per database and never overwrite a good copy with a failed one.
- `restore` refuses a corrupt backup, a locked database, and a newer schema; a valid backup restores with identical counts.
- The restore drill runs in CI: back up → corrupt → `doctor` fails → restore → `doctor` passes → counts match.
- Every migration fixture reads back all entities; the forward-version fixture is refused.
- The lifespan closes both stores; a test asserts `close()` was called.
- Online backup API only — never `shutil.copy2` on a live SQLite file.

---

## 5. Out of scope

- Encryption at rest, cloud sync, or point-in-time recovery.
- Backing up the browser's IndexedDB store.
- Compacting or rewriting the event log.

---

## 6. Verification

```bash
uv run --directory packages/core pytest
uv run --directory apps/studio-api pytest
uv run --directory apps/cli pytest
uv run ruff check . && uv run ruff format --check .
uv run mypy apps packages
```

Restore drill in CI:
1. back up the database
2. corrupt it (truncate the tail)
3. `doctor` → fails
4. `restore --from <backup> --yes`
5. `doctor` → passes
6. counts match the original

Tests to add:
- `packages/core/tests/test_sqlite_repository.py` — extend: `quick_check` at boot, `StoreCorrupt` on truncated file, no `-wal`/`-shm` after close
- `packages/core/tests/fixtures/db/*.db` — migration fixtures + generator script
- restore drill test (corrupt → restore → counts match)
- `apps/cli/tests/test_cli_doctor.py` — `doctor` durability report; `restore` refusals; dry run

## Context an implementing agent must read

- `packages/core/src/agentic_odi_core/sqlite_repository.py:40-619` — `__init__`, `_load_snapshot` (`:43`, `:46-55`), `close` (`:616-619`), event types (`:51-112`)
- `packages/core/src/agentic_odi_core/intent_store.py:40-300` — `_init_db` (`:40-75`), `_migrate`, `clear` (`:276-283`), `close` (`:294-300`), `commit` (`:285-292`)
- `packages/core/src/agentic_odi_core/errors.py` — `StoreError`, where to add `StoreCorrupt`
- `packages/core/tests/test_sqlite_repository.py:409-417, :473-483` — existing pragma and WAL tests to keep passing
- `packages/core/tests/test_events.py:11-41` — migration tests that recreate a legacy table (to be replaced by real fixtures)
- `apps/studio-api/src/agentic_odi_studio_api/app.py:62-73` — lifespan (add try/finally close)
- `apps/studio-api/src/agentic_odi_studio_api/main.py` — catch `StoreCorrupt`, print actionable line, exit non-zero
- `apps/studio-api/src/agentic_odi_studio_api/studio/memory.py:60-64, :174-190, :240-253` — `StudioMemory` open, `_MIGRATIONS`, `_init_db`, `user_version`
- `apps/cli/src/agentic_odi_cli/profile.py:103-124` — `.bak-<UTC>` convention, temp-then-replace, atomic save
- `apps/cli/src/agentic_odi_cli/cli.py:32-52, :450` — add `doctor` and `restore` commands
- #118 — `odi data export` (portability, not durability)
- #122 (closed) — committed pending transactions on shutdown (this extends it)
- #351 — diagnostics route (expose journal/WAL/checkpoint state)

## Open question for the human

Confirm whether #130's graceful shutdown already closes the DB (to avoid duplicating close logic). Also confirm the backup location default (`~/.agentic-odi/backups/` beside the database) vs a platform application-support directory — the issue proposes beside it so a user who moves the DB moves its history too.
