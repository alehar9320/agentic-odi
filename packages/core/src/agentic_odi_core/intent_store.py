"""Append-only Intent Store (CTO specification)."""

import json
import sqlite3
from datetime import datetime


class IntentStore:
    def __init__(self, db_path: str = "intent_store.db", check_same_thread: bool = True) -> None:
        # Connect to SQLite in WAL mode for high-performance concurrency
        self.conn = sqlite3.connect(db_path, check_same_thread=check_same_thread)
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self._init_db()

    def _init_db(self) -> None:
        """Creates an immutable, append-only event table."""
        with self.conn:
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload TEXT NOT NULL
                )
            """
            )

    def append(self, event_type: str, payload: dict) -> None:
        """Appends a new event to the stream (Immutable write)."""
        timestamp = datetime.utcnow().isoformat()
        payload_json = json.dumps(payload)
        with self.conn:
            self.conn.execute(
                "INSERT INTO events (timestamp, event_type, payload) VALUES (?, ?, ?)",
                (timestamp, event_type, payload_json),
            )

    def get_stream(self) -> list[dict]:
        """Retrieves the full chronological event stream for AI reasoning."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, timestamp, event_type, payload FROM events ORDER BY id ASC")
        return [
            {
                "id": row[0],
                "timestamp": row[1],
                "type": row[2],
                "payload": json.loads(row[3]) if row[3] else {},
            }
            for row in cursor.fetchall()
        ]

    def clear(self) -> None:
        """Clear all events (for testing)."""
        with self.conn:
            self.conn.execute("DELETE FROM events")

    def close(self) -> None:
        self.conn.close()
