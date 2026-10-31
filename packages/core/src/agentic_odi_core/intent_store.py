"""Append-only event store backed by SQLite."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from agentic_odi_core.errors import ConflictError, StoreError
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

#: The store's own file format version. Bump this only when a migration is
#: registered below; an additive field that needs no data change must not bump it.
CURRENT_SCHEMA_VERSION = 1

#: Migrations keyed by the version they produce: ``MIGRATIONS[n]`` upgrades a
#: store from ``n - 1`` to ``n``. They run in order inside one transaction, and
#: a step that raises rolls the whole migration back. A store whose file is
#: newer than the code is refused rather than silently downgraded.
MIGRATIONS: dict[int, Callable[[sqlite3.Connection], None]] = {}

_UPGRADE_COMMAND = "odi update"


class IntentStore:
    """SQLite implementation of the append-only event contract."""

    def __init__(self, db_path: str = "intent_store.db", check_same_thread: bool = True) -> None:
        self._db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=check_same_thread)
        self._closed = False
        try:
            # Read the stamped version before any write. Switching to WAL or
            # creating a table would rewrite the file header, and a future-version
            # refusal must leave the file byte-for-byte unchanged.
            self.conn.execute("PRAGMA busy_timeout=5000;")
            self._refuse_future_version(self._read_version())
            # WAL lets readers and one writer work at once; the busy timeout makes
            # a second writer wait for the lock (the CLI, the sidecar, and a test
            # can all hold a connection to the same file) instead of raising
            # "database is locked" the moment the lock is taken.
            self.conn.execute("PRAGMA journal_mode=WAL;")
            self._init_db()
        except sqlite3.OperationalError as exc:
            self._close_quietly()
            raise StoreError(self._unwritable_message(exc)) from exc
        except BaseException:
            self._close_quietly()
            raise

    def _unwritable_message(self, exc: sqlite3.OperationalError) -> str:
        return (
            f"the store at {self._db_path} could not be opened for writing: {exc}. "
            "Make the file and its directory writable, or point AGENTIC_ODI_DB at "
            "another path."
        )

    def _refuse_future_version(self, version: int | None) -> None:
        if version is not None and version > CURRENT_SCHEMA_VERSION:
            raise StoreError(
                f"the store at {self._db_path} was written by a newer build "
                f"(schema v{version}); this build supports schema "
                f"v{CURRENT_SCHEMA_VERSION}. Run `{_UPGRADE_COMMAND}` to upgrade, "
                "or use the newer build."
            )

    def _close_quietly(self) -> None:
        try:
            self.conn.close()
        except sqlite3.Error:
            pass

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
        self.ensure_version()

    def schema_version(self) -> int:
        """The store's own file-format version, for a surface to report.

        Reads the stamped version without writing: a caller that only wants to
        report the version must not trigger a migration or a version stamp.
        """
        version = self._read_version()
        return CURRENT_SCHEMA_VERSION if version is None else version

    def _read_version(self) -> int | None:
        """Return the stamped version, or ``None`` when no version is stamped.

        A table that holds anything other than exactly one integer version row
        is malformed metadata, not a version, so it is refused by name.
        """
        exists = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_meta'"
        ).fetchone()
        if exists is None:
            return None
        rows = self.conn.execute("SELECT version FROM schema_meta").fetchall()
        if len(rows) != 1:
            raise StoreError(
                f"the store at {self._db_path} has malformed schema_meta: "
                f"expected exactly one version row, found {len(rows)}."
            )
        value = rows[0][0]
        if isinstance(value, bool) or not isinstance(value, int):
            raise StoreError(
                f"the store at {self._db_path} has malformed schema_meta: "
                f"version is {value!r}, not an integer."
            )
        return value

    def _stamp_version(self, version: int) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_meta (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                version INTEGER NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        self.conn.execute(
            """
            INSERT INTO schema_meta (id, version, updated_at) VALUES (1, ?, ?)
            ON CONFLICT(id) DO UPDATE SET version = excluded.version,
                updated_at = excluded.updated_at
            """,
            (version, now),
        )

    def ensure_version(self) -> int:
        """Stamp or migrate the store to :data:`CURRENT_SCHEMA_VERSION`.

        A current-version store is left untouched. An older (or unstamped)
        store is migrated forward inside one transaction, so a failure leaves
        the version, the schema and the data exactly as they were. A newer
        store is refused, naming both versions and the upgrade command.
        """
        version = self._read_version()
        if version is None:
            # No stamp: today's code baseline. Stamp v1, then migrate forward.
            version = 1
            with self.conn:
                self._stamp_version(version)

        self._refuse_future_version(version)
        if version == CURRENT_SCHEMA_VERSION:
            return version

        self._migrate(version)
        return CURRENT_SCHEMA_VERSION

    def _migrate(self, from_version: int) -> None:
        # `with self.conn:` autocommits DDL in CPython's sqlite3, so an explicit
        # transaction is the only way to roll a failed migration back together
        # with its schema changes. A half-migrated event log is unrecoverable.
        self.conn.execute("BEGIN")
        try:
            for target in range(from_version + 1, CURRENT_SCHEMA_VERSION + 1):
                step = MIGRATIONS.get(target)
                if step is None:
                    raise StoreError(
                        f"no migration registered for schema v{target} "
                        f"(store at {self._db_path} is at v{from_version}); "
                        "this build is missing a migration step."
                    )
                step(self.conn)
            self._stamp_version(CURRENT_SCHEMA_VERSION)
        except BaseException:
            self.conn.execute("ROLLBACK")
            raise
        self.conn.execute("COMMIT")

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
        unsynced_only: bool = False,
        replay_order: bool = False,
    ) -> list[Event]:
        clauses: list[str] = []
        params: list[Any] = []
        if workspace_id is not None:
            clauses.append("workspace_id = ?")
            params.append(workspace_id)
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
