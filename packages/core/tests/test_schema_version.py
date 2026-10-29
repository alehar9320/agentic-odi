"""ALH-53 / F1 — a schema version you can migrate.

The store owns its own file format: it stamps `schema_meta.version` on open,
migrates an older file forward inside one transaction, and refuses a file
written by a newer build before touching a byte of it.
"""

from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

import pytest
from agentic_odi_core import intent_store
from agentic_odi_core.errors import StoreError
from agentic_odi_core.intent_store import CURRENT_SCHEMA_VERSION, IntentStore

FIXTURES = Path(__file__).parent / "fixtures"


def _fresh(db: Path, dest: Path) -> Path:
    """Copy a committed fixture into the test's tmp dir so it is never mutated."""
    target = dest / db.name
    shutil.copy(db, target)
    return target


def _create_legacy_db(path: Path) -> None:
    """A pre-version store: events exist, `schema_meta` does not."""
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
        "INSERT INTO events (event_id, timestamp, event_type, payload)"
        " VALUES ('e1', '2026-01-01T00:00:00+00:00', 'JOB_CREATED', '{\"id\": \"j1\"}')"
    )
    conn.commit()
    conn.close()


def _create_future_db(path: Path, version: int) -> None:
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
        "CREATE TABLE schema_meta ("
        "id INTEGER PRIMARY KEY CHECK (id = 1), "
        "version INTEGER NOT NULL, updated_at TEXT NOT NULL)"
    )
    conn.execute(
        "INSERT INTO schema_meta (id, version, updated_at) VALUES (1, ?, '2026-01-01T00:00:00+00:00')",
        (version,),
    )
    conn.commit()
    conn.close()


def _stored_version(db: Path) -> int:
    conn = sqlite3.connect(db)
    try:
        return int(conn.execute("SELECT version FROM schema_meta").fetchone()[0])
    finally:
        conn.close()


def _updated_at(db: Path) -> str:
    conn = sqlite3.connect(db)
    try:
        return str(conn.execute("SELECT updated_at FROM schema_meta").fetchone()[0])
    finally:
        conn.close()


def test_new_database_is_stamped_with_the_current_version(tmp_path: Path) -> None:
    store = IntentStore(str(tmp_path / "odi.db"))
    try:
        assert _stored_version(tmp_path / "odi.db") == CURRENT_SCHEMA_VERSION
    finally:
        store.close()


def test_reopening_a_current_database_does_not_rewrite_metadata(tmp_path: Path) -> None:
    db = tmp_path / "odi.db"
    first = IntentStore(str(db))
    first.close()
    stamped = _updated_at(db)

    second = IntentStore(str(db))
    second.close()

    assert _updated_at(db) == stamped


def test_legacy_database_is_bootstrapped_exactly_once(tmp_path: Path) -> None:
    db = _fresh(FIXTURES / "legacy_v0.db", tmp_path)

    store = IntentStore(str(db))
    try:
        assert _stored_version(db) == CURRENT_SCHEMA_VERSION
        assert [e["type"] for e in store.get_stream()] == ["JOB_CREATED"]
    finally:
        store.close()
    stamped = _updated_at(db)

    reopened = IntentStore(str(db))
    reopened.close()

    assert _updated_at(db) == stamped


def test_future_version_is_refused_naming_both_versions(tmp_path: Path) -> None:
    db = _fresh(FIXTURES / "future_v99.db", tmp_path)
    before = db.read_bytes()

    with pytest.raises(StoreError) as excinfo:
        IntentStore(str(db))

    message = str(excinfo.value)
    assert "99" in message
    assert str(CURRENT_SCHEMA_VERSION) in message
    assert "odi update" in message
    assert db.read_bytes() == before, "a refusal must not mutate the file"


def test_injected_later_migration_failure_rolls_everything_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = tmp_path / "odi.db"
    store = IntentStore(str(db))
    try:

        def step_two(conn: sqlite3.Connection) -> None:
            conn.execute("CREATE TABLE m2_marker (x INTEGER)")
            conn.execute("INSERT INTO m2_marker VALUES (1)")

        def step_three(conn: sqlite3.Connection) -> None:
            raise RuntimeError("injected failure")

        monkeypatch.setattr(intent_store, "CURRENT_SCHEMA_VERSION", 3)
        monkeypatch.setattr(intent_store, "MIGRATIONS", {2: step_two, 3: step_three})

        with pytest.raises(RuntimeError):
            store.ensure_version()

        assert _stored_version(db) == 1
        tables = {
            row[0]
            for row in store.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "m2_marker" not in tables
    finally:
        store.close()

    # The original store is still openable by its compatible version: undo the
    # synthetic migration registry, then reopen at the real baseline.
    monkeypatch.undo()
    reopened = IntentStore(str(db))
    try:
        assert _stored_version(db) == CURRENT_SCHEMA_VERSION
        assert [e["type"] for e in reopened.get_stream()] == []
    finally:
        reopened.close()


def test_missing_registry_step_fails_without_partial_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = tmp_path / "odi.db"
    store = IntentStore(str(db))
    try:

        def step_two(conn: sqlite3.Connection) -> None:
            conn.execute("CREATE TABLE m2_marker (x INTEGER)")

        monkeypatch.setattr(intent_store, "CURRENT_SCHEMA_VERSION", 3)
        monkeypatch.setattr(intent_store, "MIGRATIONS", {2: step_two})

        with pytest.raises(StoreError) as excinfo:
            store.ensure_version()

        assert "3" in str(excinfo.value)
        assert _stored_version(db) == 1
        tables = {
            row[0]
            for row in store.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "m2_marker" not in tables
    finally:
        store.close()


def test_duplicate_version_metadata_is_refused(tmp_path: Path) -> None:
    db = tmp_path / "odi.db"
    _create_legacy_db(db)
    conn = sqlite3.connect(db)
    # A hand-crafted table with no CHECK constraint can hold two rows.
    conn.execute("CREATE TABLE schema_meta (version INTEGER NOT NULL, updated_at TEXT NOT NULL)")
    conn.execute("INSERT INTO schema_meta VALUES (1, 'a'), (1, 'b')")
    conn.commit()
    conn.close()

    with pytest.raises(StoreError) as excinfo:
        IntentStore(str(db))

    assert "schema_meta" in str(excinfo.value) or "version" in str(excinfo.value)


def test_read_only_database_fails_with_an_actionable_message(tmp_path: Path) -> None:
    db = tmp_path / "odi.db"
    _create_legacy_db(db)
    db.chmod(0o444)
    tmp_path.chmod(0o555)
    try:
        with pytest.raises(StoreError) as excinfo:
            IntentStore(str(db))
        assert "read" in str(excinfo.value).lower() or "writ" in str(excinfo.value).lower()
    finally:
        tmp_path.chmod(0o755)
