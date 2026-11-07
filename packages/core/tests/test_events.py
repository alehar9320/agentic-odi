"""Tests for the new event-store schema and migration."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest
from agentic_odi_core.events import default_device_path, resolve_device_id
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


@pytest.fixture
def no_configured_device(monkeypatch) -> None:
    monkeypatch.delenv("AGENTIC_ODI_DEVICE_ID", raising=False)


@pytest.mark.usefixtures("no_configured_device")
def test_the_device_id_is_created_once_and_reused(tmp_path) -> None:
    path = tmp_path / ".agentic-odi" / "device_id"

    first = resolve_device_id(path)
    second = resolve_device_id(path)

    assert first == second
    assert path.read_text(encoding="utf-8").strip() == first


@pytest.mark.usefixtures("no_configured_device")
def test_the_device_id_names_nobody(tmp_path) -> None:
    import getpass
    import socket

    device_id = resolve_device_id(tmp_path / "device_id")

    assert len(device_id) == 32
    assert set(device_id) <= set("0123456789abcdef")
    for secret in (getpass.getuser(), socket.gethostname()):
        if secret:
            assert secret.replace("-", "") not in device_id


@pytest.mark.usefixtures("no_configured_device")
def test_two_installs_get_two_device_ids(tmp_path) -> None:
    one = resolve_device_id(tmp_path / "a" / "device_id")
    two = resolve_device_id(tmp_path / "b" / "device_id")

    assert one != two


@pytest.mark.usefixtures("no_configured_device")
def test_the_device_id_file_is_owner_readable_only(tmp_path) -> None:
    path = tmp_path / "device_id"

    resolve_device_id(path)

    assert path.stat().st_mode & 0o777 == 0o600


@pytest.mark.usefixtures("no_configured_device")
def test_the_device_id_lives_under_the_agentic_odi_home(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))

    assert default_device_path() == tmp_path / ".agentic-odi" / "device_id"


def test_a_configured_device_id_wins_and_writes_nothing(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AGENTIC_ODI_DEVICE_ID", "device-from-env")
    path = tmp_path / "device_id"

    assert resolve_device_id(path) == "device-from-env"
    assert not path.exists()


def test_appends_remember_which_device_wrote_them(tmp_path) -> None:
    store = IntentStore(str(Path(tmp_path) / "odi.db"))

    store.append("JOB_CREATED", {"id": "j1"}, workspace_id="acme", device_id="device-a")
    event = store.get_stream()[0]

    assert event["workspace_id"] == "acme"
    assert event["device_id"] == "device-a"
    assert os.sep not in event["device_id"]
    store.close()
