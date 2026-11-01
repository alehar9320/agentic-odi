"""Append-only event store backed by SQLite."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from agentic_odi_core.errors import ConflictError, SchemaVersionError, StoreError
from agentic_odi_core.events import (
    DEFAULT_DEVICE,
    DEFAULT_WORKSPACE,
    Event,
    new_event_id,
)

_COLUMNS = {
    "event_id": "TEXT",
    "workspace_id": "TEXT NOT NULL DEFAULT 'local'",
    "device_id": "TEXT NOT NULL DEFAULT 'local'",
    "server_seq": "INTEGER",
}

CURRENT_SCHEMA_VERSION = 1

Migration = Callable[[sqlite3.Connection], None]


def _bootstrap_schema_meta(conn: sqlite3.Connection) -> None:
    """v1: give the store a version table. Legacy databases are otherwise unchanged."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_meta (
            version INTEGER NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "INSERT OR IGNORE INTO schema_meta (version, updated_at) VALUES (?, ?)",
        (1, datetime.now(timezone.utc).isoformat()),
    )


MIGRATIONS: dict[int, Migration] = {1: _bootstrap_schema_meta}


class IntentStore:
    """SQLite implementation of the append-only event contract."""

    def __init__(self, db_path: str = "intent_store.db", check_same_thread: bool = True) -> None:
        self.conn = sqlite3.connect(db_path, check_same_thread=check_same_thread)
        self.conn.execute("PRAGMA busy_timeout=5000;")
        self._closed = False
        self.schema_version = 0
        try:
            # The version gate runs before any write, including the WAL pragma
            # below (which rewrites the file header): a refusal must leave the
            # store's bytes untouched.
            self.ensure_version()
            try:
                # WAL lets readers and one writer work at once; the busy timeout
                # makes a second writer wait for the lock (the CLI, the sidecar,
                # and a test can all hold a connection to the same file) instead
                # of raising "database is locked" the moment the lock is taken.
                self.conn.execute("PRAGMA journal_mode=WAL;")
            except sqlite3.OperationalError as err:
                raise StoreError(
                    f"store file is not writable ({err}); the store needs write access "
                    "to its file and directory"
                ) from err
            self._init_db()
        except Exception:
            self.conn.close()
            self._closed = True
            raise

    def ensure_version(self) -> int:
        """Read, migrate, or refuse the on-disk schema version. Called on open."""
        version = self._read_stored_version()
        if version > CURRENT_SCHEMA_VERSION:
            raise SchemaVersionError(
                f"database schema version {version} is newer than this build supports "
                f"(version {CURRENT_SCHEMA_VERSION}); run `odi update` to upgrade, then retry"
            )
        if version == CURRENT_SCHEMA_VERSION:
            self.schema_version = version
            return version

        missing = [
            step
            for step in range(version + 1, CURRENT_SCHEMA_VERSION + 1)
            if step not in MIGRATIONS
        ]
        if missing:
            raise SchemaVersionError(
                f"database schema version {version} cannot reach version "
                f"{CURRENT_SCHEMA_VERSION}: no registered migration for step {missing[0]}. "
                f"Steps {missing} are missing from the registry; reinstall a build that "
                "registers them or `odi update`"
            )
        # Python's implicit transaction handling only opens a transaction before
        # DML, so a migration's CREATE/ALTER TABLE would commit on its own and
        # survive a later step's failure. Drive BEGIN/COMMIT/ROLLBACK explicitly.
        self._run_migrations(version)
        self.schema_version = self._read_stored_version()
        return self.schema_version

    def _run_migrations(self, version: int) -> None:
        previous_isolation = self.conn.isolation_level
        self.conn.isolation_level = None
        try:
            try:
                self.conn.execute("BEGIN")
                for step in range(version + 1, CURRENT_SCHEMA_VERSION + 1):
                    MIGRATIONS[step](self.conn)
            except Exception as err:
                self.conn.execute("ROLLBACK")
                raise self._migration_error(version, err) from err
            else:
                self.conn.execute("COMMIT")
        finally:
            self.conn.isolation_level = previous_isolation

    def _migration_error(self, version: int, err: Exception) -> StoreError:
        if isinstance(err, sqlite3.OperationalError):
            return SchemaVersionError(
                f"store at version {version} needs a migration to version "
                f"{CURRENT_SCHEMA_VERSION}, but the database file is not writable "
                f"({err}); grant write permission to the store file or its directory"
            )
        return StoreError(
            f"migration to version {CURRENT_SCHEMA_VERSION} failed: {err}; "
            f"the store is unchanged at version {version}"
        )

    def _read_stored_version(self) -> int:
        """0 for a legacy store that predates schema_meta; otherwise the stored version."""
        has_meta = self.conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_meta'"
        ).fetchone()
        if not has_meta:
            return 0
        rows = self.conn.execute("SELECT version FROM schema_meta").fetchall()
        if not rows:
            raise SchemaVersionError(
                "schema_meta table exists but records no version; the store is malformed. "
                "Restore the database from a backup or open it with the version that created it"
            )
        if len(rows) != 1:
            raise SchemaVersionError(
                f"schema_meta records {len(rows)} versions; exactly one row is expected. "
                "The store is malformed; restore the database from a backup"
            )
        version = rows[0][0]
        if not isinstance(version, int) or isinstance(version, bool):
            raise SchemaVersionError(
                f"schema_meta records a non-integer version {version!r}; the store is "
                "malformed. Restore the database from a backup"
            )
        if version < 1:
            raise SchemaVersionError(
                f"schema_meta records version {version}, which is not a valid schema "
                "version (versions start at 1); the store is malformed. Restore the "
                "database from a backup"
            )
        return int(version)

    def _init_db(self) -> None:
        with self.conn:
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT,
                    workspace_id TEXT NOT NULL DEFAULT 'local',
                    device_id TEXT NOT NULL DEFAULT 'local',
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    server_seq INTEGER
                )
                """
            )
            self._migrate_events_table()
            self.conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS events_event_id ON events(event_id)"
            )
            self.conn.execute(
                """
                CREATE INDEX IF NOT EXISTS events_workspace_server
                ON events(workspace_id, server_seq)
                """
            )
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sync_state (
                    workspace_id TEXT PRIMARY KEY,
                    remote_url TEXT NOT NULL DEFAULT '',
                    last_server_seq INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def _migrate_events_table(self) -> None:
        existing = {row[1] for row in self.conn.execute("PRAGMA table_info(events)").fetchall()}
        for column, definition in _COLUMNS.items():
            if column not in existing:
                self.conn.execute(f"ALTER TABLE events ADD COLUMN {column} {definition}")

        missing_ids = [
            row[0]
            for row in self.conn.execute(
                "SELECT id FROM events WHERE event_id IS NULL OR event_id = ''"
            ).fetchall()
        ]
        for row_id in missing_ids:
            self.conn.execute(
                "UPDATE events SET event_id = ? WHERE id = ?",
                (new_event_id(), row_id),
            )

    def append(
        self,
        event_type: str,
        payload: dict[str, Any],
        *,
        event_id: str | None = None,
        workspace_id: str = DEFAULT_WORKSPACE,
        device_id: str = DEFAULT_DEVICE,
    ) -> Event:
        resolved_id = event_id or new_event_id()
        timestamp = datetime.now(timezone.utc).isoformat()
        payload_json = json.dumps(payload)
        with self.conn:
            self.conn.execute(
                """
                INSERT OR IGNORE INTO events
                    (event_id, workspace_id, device_id, timestamp, event_type, payload)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (resolved_id, workspace_id, device_id, timestamp, event_type, payload_json),
            )
            row = self.conn.execute(
                """
                SELECT id, event_id, workspace_id, device_id, timestamp,
                       event_type, payload, server_seq
                FROM events WHERE event_id = ?
                """,
                (resolved_id,),
            ).fetchone()

        if row is None:
            raise StoreError(f"event {resolved_id} could not be stored")
        if row[2] != workspace_id:
            raise ConflictError(f"event_id {resolved_id} already belongs to another workspace")
        return self._to_event(row)

    def get_stream(
        self,
        *,
        workspace_id: str | None = None,
        after_server_seq: int = 0,
        after_id: int = 0,
        unsynced_only: bool = False,
        replay_order: bool = False,
    ) -> list[Event]:
        clauses: list[str] = []
        params: list[Any] = []
        if workspace_id is not None:
            clauses.append("workspace_id = ?")
            params.append(workspace_id)
        if after_id:
            # The rowid is the append order, so this is a covering range scan
            # from the last event already applied rather than a full replay.
            clauses.append("id > ?")
            params.append(after_id)
        if after_server_seq:
            clauses.append("server_seq IS NOT NULL AND server_seq > ?")
            params.append(after_server_seq)
        if unsynced_only:
            clauses.append("server_seq IS NULL")

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        if replay_order:
            order = "ORDER BY (server_seq IS NULL) ASC, server_seq ASC, id ASC"
        else:
            order = "ORDER BY id ASC"

        cursor = self.conn.cursor()
        # `where` and `order` are assembled from the literal fragments above, so
        # interpolating them cannot inject SQL; every caller value is bound.
        sql = (
            "SELECT id, event_id, workspace_id, device_id, timestamp, "
            "event_type, payload, server_seq FROM events "
            f"{where} {order}"  # nosec B608 - static fragments, bound values
        )
        cursor.execute(sql, params)
        return [self._to_event(row) for row in cursor.fetchall()]

    @staticmethod
    def _to_event(row: tuple[Any, ...]) -> Event:
        return Event(
            id=row[0],
            event_id=row[1],
            workspace_id=row[2],
            device_id=row[3],
            timestamp=row[4],
            type=row[5],
            payload=json.loads(row[6]) if row[6] else {},
            server_seq=row[7],
        )

    def insert_remote(self, events: list[Event]) -> int:
        inserted = 0
        with self.conn:
            for event in events:
                self.conn.execute(
                    """
                    INSERT OR IGNORE INTO events
                        (event_id, workspace_id, device_id, timestamp,
                         event_type, payload, server_seq)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event["event_id"],
                        event["workspace_id"],
                        event["device_id"],
                        event["timestamp"],
                        event["type"],
                        json.dumps(event["payload"]),
                        event.get("server_seq"),
                    ),
                )
                self.conn.execute(
                    """
                    UPDATE events SET server_seq = ?
                    WHERE event_id = ? AND server_seq IS NULL AND workspace_id = ?
                    """,
                    (
                        event.get("server_seq"),
                        event["event_id"],
                        event["workspace_id"],
                    ),
                )
                inserted += 1
        return inserted

    def mark_synced(self, server_seqs: dict[str, int]) -> int:
        updated = 0
        with self.conn:
            for event_id, server_seq in server_seqs.items():
                cursor = self.conn.execute(
                    "UPDATE events SET server_seq = ? WHERE event_id = ? AND server_seq IS NULL",
                    (server_seq, event_id),
                )
                updated += cursor.rowcount
        return updated

    def retag_workspace(self, old: str, new: str) -> int:
        updated = 0
        with self.conn:
            cursor = self.conn.execute(
                "UPDATE events SET workspace_id = ? WHERE workspace_id = ?",
                (new, old),
            )
            updated = cursor.rowcount
            self.conn.execute(
                "DELETE FROM sync_state WHERE workspace_id = ?",
                (old,),
            )
        return updated

    def max_server_seq(self, workspace_id: str) -> int:
        row = self.conn.execute(
            "SELECT COALESCE(MAX(server_seq), 0) FROM events WHERE workspace_id = ?",
            (workspace_id,),
        ).fetchone()
        return int(row[0]) if row else 0

    def get_cursor(self, workspace_id: str) -> int:
        row = self.conn.execute(
            "SELECT last_server_seq FROM sync_state WHERE workspace_id = ?",
            (workspace_id,),
        ).fetchone()
        return int(row[0]) if row else 0

    def set_cursor(self, workspace_id: str, remote_url: str, seq: int) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO sync_state (workspace_id, remote_url, last_server_seq, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(workspace_id) DO UPDATE SET
                    remote_url = excluded.remote_url,
                    last_server_seq = excluded.last_server_seq,
                    updated_at = excluded.updated_at
                """,
                (workspace_id, remote_url, seq, now),
            )

    def pending_count(self, workspace_id: str) -> int:
        row = self.conn.execute(
            "SELECT COUNT(*) FROM events WHERE workspace_id = ? AND server_seq IS NULL",
            (workspace_id,),
        ).fetchone()
        return int(row[0]) if row else 0

    def clear(self, *, workspace_id: str | None = None) -> None:
        with self.conn:
            if workspace_id is None:
                self.conn.execute("DELETE FROM events")
                self.conn.execute("DELETE FROM sync_state")
            else:
                self.conn.execute("DELETE FROM events WHERE workspace_id = ?", (workspace_id,))
                self.conn.execute("DELETE FROM sync_state WHERE workspace_id = ?", (workspace_id,))

    def commit(self) -> None:
        """Flush any open transaction to disk.

        :meth:`append` already commits every event as it is written, so this is
        normally a no-op. It exists so a shutdown path can assert durability
        explicitly rather than assuming it.
        """
        self.conn.commit()

    def close(self) -> None:
        """Close the connection. Safe to call more than once."""
        if self._closed:
            return
        self._closed = True
        self.conn.commit()
        self.conn.close()
