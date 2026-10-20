"""Tests for the new event-store schema and migration."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from agentic_odi_core.intent_store import IntentStore


def test_legacy_db_backfill_adds_event_id_and_spaces(tmp_path) -> None:
    """An existing `odi.db` without `event_id` columns must be upgraded."""
    db = Path(tmp_path) / "odi.db"
    conn = sqlite3.connect(db)
    conn.execute(
        """
        CREATE TABLE events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            event_type TEXT NOT NULL,
            payload TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "INSERT INTO events (timestamp, event_type, payload) VALUES ('2026-01-01T00:00:00', 'JOB_CREATED', '{\"id\": \"j1\"}')"
    )
    conn.commit()
    conn.close()

    store = IntentStore(str(db))
    events = store.get_stream()
    # The migration must have added event_id, workspace_id, device_id columns,
    # backfilled them, and the row must contain them.
    assert len(events) == 1
    ev = events[0]
    assert ev["event_id"]
    assert ev["workspace_id"] == "local"
    assert ev["device_id"] == "local"
    assert ev["server_seq"] is None
    store.close()


def test_new_db_has_all_columns(tmp_path) -> None:
    """A freshly created DB must contain all new event columns."""
    db = Path(tmp_path) / "odi.db"
    store = IntentStore(str(db))
    events = store.get_stream()
    assert len(events) == 0
    # Verify schema contains all new columns via PRAGMA introspection.
    # (the constructor runs _migrate_events_table and adds columns.)
    conn = sqlite3.connect(str(db))
    cols = {row[1] for row in conn.execute("PRAGMA table_info(events)").fetchall()}
    assert "event_id" in cols, f"Missing event_id column, got: {cols}"
    assert "workspace_id" in cols
    assert "device_id" in cols
    assert "server_seq" in cols
    conn.close()
    store.close()