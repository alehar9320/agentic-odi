"""ALH-53: the intent store carries a schema version and a migration registry."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest
from agentic_odi_core import intent_store as intent_store_module
from agentic_odi_core.errors import SchemaVersionError, StoreError, error_status
from agentic_odi_core.intent_store import CURRENT_SCHEMA_VERSION, IntentStore

FIXTURES = Path(__file__).resolve().parents[3] / "tests" / "fixtures"


def _make_legacy_db(path: Path) -> None:
    """A v0 database: today's tables, no schema_meta, one event."""
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE events (
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
    conn.execute(
        "INSERT INTO events (event_id, timestamp, event_type, payload) "
        "VALUES ('ev-legacy', '2026-01-01T00:00:00+00:00', 'JOB_CREATED', '{}')"
    )
    conn.execute(
        """
        CREATE TABLE sync_state (
            workspace_id TEXT PRIMARY KEY,
            remote_url TEXT NOT NULL DEFAULT '',
            last_server_seq INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def _make_db_at_version(path: Path, version: int) -> None:
    _make_legacy_db(path)
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE schema_meta (version INTEGER NOT NULL, updated_at TEXT NOT NULL)")
    conn.execute("INSERT INTO schema_meta (version, updated_at) VALUES (?, ?)", (version, "x"))
    conn.commit()
    conn.close()


def _stored_versions(path: Path) -> list[tuple[object, object]]:
    conn = sqlite3.connect(path)
    try:
        return conn.execute("SELECT version, updated_at FROM schema_meta").fetchall()
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()


def _table_names(path: Path) -> set[str]:
    conn = sqlite3.connect(path)
    try:
        return {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        conn.close()


def test_fresh_store_opens_at_current_version(tmp_path) -> None:
    db = tmp_path / "odi.db"
    store = IntentStore(str(db))
    try:
        assert store.schema_version == CURRENT_SCHEMA_VERSION == 1
    finally:
        store.close()
    assert [row[0] for row in _stored_versions(db)] == [1]


def test_legacy_db_migrates_to_v1_and_keeps_events(tmp_path) -> None:
    db = tmp_path / "legacy.db"
    _make_legacy_db(db)

    store = IntentStore(str(db))
    try:
        assert store.schema_version == CURRENT_SCHEMA_VERSION == 1
        assert [event["event_id"] for event in store.get_stream()] == ["ev-legacy"]
    finally:
        store.close()

    assert [row[0] for row in _stored_versions(db)] == [1]


def test_reopening_current_db_runs_no_migrations_and_writes_no_version(tmp_path) -> None:
    db = tmp_path / "odi.db"
    IntentStore(str(db)).close()
    before = _stored_versions(db)

    calls: list[int] = []

    def spy(step: int):
        def run(_conn: sqlite3.Connection) -> None:
            calls.append(step)

        return run

    patched = {step: spy(step) for step in range(1, CURRENT_SCHEMA_VERSION + 5)}
    original = intent_store_module.MIGRATIONS
    intent_store_module.MIGRATIONS = patched
    try:
        IntentStore(str(db)).close()
    finally:
        intent_store_module.MIGRATIONS = original

    assert calls == [], "reopening a current-version db must not run any migration step"
    assert _stored_versions(db) == before, "reopening must not rewrite schema_meta"


def test_future_version_db_is_refused_naming_both_versions(tmp_path) -> None:
    db = tmp_path / "future.db"
    _make_db_at_version(db, 99)

    with pytest.raises(StoreError) as excinfo:
        IntentStore(str(db))

    message = str(excinfo.value)
    assert "99" in message and str(CURRENT_SCHEMA_VERSION) in message
    assert "odi update" in message


def test_v99_refusal_leaves_file_bytes_unchanged(tmp_path) -> None:
    db = tmp_path / "copy.db"
    db.write_bytes((FIXTURES / "schema_v99.db").read_bytes())
    before = db.read_bytes()

    with pytest.raises(SchemaVersionError):
        IntentStore(str(db))

    assert db.read_bytes() == before


def test_legacy_fixture_migrates_to_v1(tmp_path) -> None:
    db = tmp_path / "copy.db"
    db.write_bytes((FIXTURES / "schema_legacy_v0.db").read_bytes())

    store = IntentStore(str(db))
    try:
        assert store.schema_version == 1 == CURRENT_SCHEMA_VERSION
    finally:
        store.close()


def test_failing_migration_rolls_back_data_schema_and_version(tmp_path) -> None:
    db = tmp_path / "odi.db"
    store = IntentStore(str(db))
    store.append("JOB_CREATED", {"id": "job-1"})
    store.close()

    def step_two(conn: sqlite3.Connection) -> None:
        conn.execute("CREATE TABLE scratch (value TEXT)")
        conn.execute("INSERT INTO scratch VALUES ('from-step-two')")

    def step_three(conn: sqlite3.Connection) -> None:
        conn.execute(
            "INSERT INTO events (event_id, timestamp, event_type, payload) "
            "VALUES ('ev-partial', '2026-01-01T00:00:00+00:00', 'NOPE', '{}')"
        )
        raise RuntimeError("injected failure")

    original_registry = dict(intent_store_module.MIGRATIONS)
    original_version = intent_store_module.CURRENT_SCHEMA_VERSION
    intent_store_module.MIGRATIONS.update({2: step_two, 3: step_three})
    intent_store_module.CURRENT_SCHEMA_VERSION = 3
    try:
        with pytest.raises(StoreError):
            IntentStore(str(db))

        assert [row[0] for row in _stored_versions(db)] == [1], (
            "version must stay at the last good value"
        )
        assert "scratch" not in _table_names(db), "earlier migration schema must roll back"
    finally:
        intent_store_module.MIGRATIONS.clear()
        intent_store_module.MIGRATIONS.update(original_registry)
        intent_store_module.CURRENT_SCHEMA_VERSION = original_version

    reopened = IntentStore(str(db))
    try:
        events = list(reopened.get_stream())
    finally:
        reopened.close()
    assert "ev-partial" not in [event["event_id"] for event in events], (
        "partial migration data must roll back"
    )
    assert "job-1" in [event["payload"]["id"] for event in events]


def test_missing_registry_step_fails_with_actionable_message(tmp_path, monkeypatch) -> None:
    db = tmp_path / "odi.db"
    IntentStore(str(db)).close()

    monkeypatch.setattr(intent_store_module, "CURRENT_SCHEMA_VERSION", 3)
    with pytest.raises(SchemaVersionError) as excinfo:
        IntentStore(str(db))
    assert "2" in str(excinfo.value), "message must name the missing step"
    assert [row[0] for row in _stored_versions(db)] == [1]


@pytest.mark.parametrize(
    "bad_rows",
    [
        [("0", "x")],
        [(-3, "x")],
        [("not-a-number", "x")],
        [(1, "a"), (1, "b")],
    ],
    ids=["zero", "negative", "non-integer", "duplicate-rows"],
)
def test_malformed_and_duplicate_version_metadata_fail(tmp_path, bad_rows) -> None:
    db = tmp_path / "bad.db"
    _make_legacy_db(db)
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE schema_meta (version INTEGER NOT NULL, updated_at TEXT NOT NULL)")
    conn.executemany("INSERT INTO schema_meta VALUES (?, ?)", bad_rows)
    conn.commit()
    conn.close()

    with pytest.raises(SchemaVersionError) as excinfo:
        IntentStore(str(db))
    assert str(excinfo.value).strip(), "refusal must explain itself, never a bare message"
    # schema_meta has INTEGER affinity, so SQLite stores a numeric string as its int.
    assert _stored_versions(db) == [
        (int(row[0]) if str(row[0]).lstrip("-").isdigit() else row[0], row[1]) for row in bad_rows
    ]


def test_read_only_store_that_needs_migration_fails_actionably(tmp_path) -> None:
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        pytest.skip("read-only permissions are not enforceable as root")
    db = tmp_path / "odi.db"
    _make_legacy_db(db)
    db.chmod(0o444)

    with pytest.raises(StoreError) as excinfo:
        IntentStore(str(db))
    assert "read-only" in str(excinfo.value) or "permission" in str(excinfo.value)


def test_schema_version_error_is_a_store_error() -> None:
    assert isinstance(SchemaVersionError("x"), StoreError)
    assert error_status(SchemaVersionError("x")) == 500
