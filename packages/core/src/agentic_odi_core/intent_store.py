"""Append-only event store backed by SQLite."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

from agentic_odi_core.errors import ConflictError, StoreCorrupt, StoreError
from agentic_odi_core.events import (
    DEFAULT_DEVICE,
    DEFAULT_WORKSPACE,
    Event,
    new_event_id,
)
from agentic_odi_core.integrity import IntegrityResult, ensure_intact

_COLUMNS = {
    "event_id": "TEXT",
    "workspace_id": "TEXT NOT NULL DEFAULT 'local'",
    "device_id": "TEXT NOT NULL DEFAULT 'local'",
    "server_seq": "INTEGER",
}


class IntentStore:
    """SQLite implementation of the append-only event contract."""

    def __init__(
        self,
        db_path: str = "intent_store.db",
        check_same_thread: bool = True,
        *,
        label: str = "Your database",
    ) -> None:
        self.conn = sqlite3.connect(db_path, check_same_thread=check_same_thread)
        self._closed = False
        try:
            # Gate the boot before anything else touches the file. A pragma or a
            # migration on a damaged file raises a bare DatabaseError; the gate
            # turns that into an actionable StoreCorrupt that names the file.
            self.integrity: IntegrityResult = ensure_intact(self.conn, db_path, label=label)
            # WAL lets readers and one writer work at once; the busy timeout makes
            # a second writer wait for the lock (the CLI, the sidecar, and a test
            # can all hold a connection to the same file) instead of raising
            # "database is locked" the moment the lock is taken.
            self.conn.execute("PRAGMA journal_mode=WAL;")
            self.conn.execute("PRAGMA busy_timeout=5000;")
            self._init_db()
        except sqlite3.DatabaseError as exc:
            self.conn.close()
            raise StoreCorrupt(db_path, [str(exc)], label=label) from exc
        except BaseException:
            self.conn.close()
            raise

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
        # A bulk delete leaves a large log behind; fold it back now rather than
        # waiting for the next auto-checkpoint.
        self.checkpoint("PASSIVE")

    def commit(self) -> None:
        """Flush any open transaction to disk.

        :meth:`append` already commits every event as it is written, so this is
        normally a no-op. It exists so a shutdown path can assert durability
        explicitly rather than assuming it.
        """
        self.conn.commit()

    def checkpoint(self, mode: str = "TRUNCATE") -> None:
        """Fold the write-ahead log back into the database file.

        ``TRUNCATE`` empties the log after a checkpoint, so a clean shutdown
        leaves no ``-wal`` for a later process to recover. ``PASSIVE`` is for
        the idle case: it does what it can without waiting on readers. Both are
        bounded by the connection's ``busy_timeout`` so a contended checkpoint
        cannot hang the caller. Safe to call after close and on a memory store.
        """
        if self._closed:
            return
        try:
            self.conn.execute(f"PRAGMA wal_checkpoint({mode})").fetchall()
        except sqlite3.Error:
            # A checkpoint is best-effort durability, not a write. A store that
            # cannot checkpoint (in-memory, or a reader holding the log) still
            # closes cleanly; the next open will recover the log.
            pass

    def close(self) -> None:
        """Checkpoint the log, then close the connection. Safe to call twice."""
        if self._closed:
            return
        self.checkpoint("TRUNCATE")
        self._closed = True
        self.conn.commit()
        self.conn.close()
