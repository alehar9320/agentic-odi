"""The migration ledger: numbered, recorded, and gapless.

These tests run on ``:memory:`` connections and on a fixture that matches the
pre-ledger shape. Nothing here opens ``~/.agentic-odi/odi.db`` — the point of a
fixture is that the test never touches the only copy of anyone's data.
"""

from __future__ import annotations

import sqlite3

import pytest
from agentic_odi_core.errors import MigrationError
from agentic_odi_core.intent_store import IntentStore
from agentic_odi_core.migrations import (
    CURRENT_VERSION,
    MIGRATIONS,
    Migration,
    current_version,
    migrate,
    migration_steps,
)


def _legacy_events_connection() -> sqlite3.Connection:
    """A v0 ``odi.db``: the ``events`` table before the identity columns.

    Built from an explicit ``CREATE TABLE`` rather than a committed binary so
    the pre-change shape is readable in the test that depends on it.
    """
    connection = sqlite3.connect(":memory:")
    connection.execute(
        """
        CREATE TABLE events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            event_type TEXT NOT NULL,
            payload TEXT NOT NULL
        )
        """
    )
    connection.execute(
        "INSERT INTO events (timestamp, event_type, payload) "
        "VALUES ('2026-01-01T00:00:00', 'JOB_CREATED', '{\"id\": \"j1\"}')"
    )
    connection.execute(
        "INSERT INTO events (timestamp, event_type, payload) "
        "VALUES ('2026-01-02T00:00:00', 'STEP_CREATED', '{\"id\": \"s1\"}')"
    )
    connection.commit()
    return connection


def test_a_fresh_database_ends_at_the_current_version() -> None:
    connection = sqlite3.connect(":memory:")
    connection.execute("CREATE TABLE events (id INTEGER PRIMARY KEY AUTOINCREMENT)")

    assert current_version(connection) == 0
    assert migrate(connection, MIGRATIONS) == CURRENT_VERSION
    assert current_version(connection) == CURRENT_VERSION


def test_a_second_open_is_a_no_op() -> None:
    connection = sqlite3.connect(":memory:")
    connection.execute("CREATE TABLE events (id INTEGER PRIMARY KEY AUTOINCREMENT)")
    migrate(connection, MIGRATIONS)

    before = connection.execute("SELECT count(*) FROM events").fetchone()[0]
    assert migrate(connection, MIGRATIONS) == CURRENT_VERSION
    assert current_version(connection) == CURRENT_VERSION
    assert connection.execute("SELECT count(*) FROM events").fetchone()[0] == before


def test_a_legacy_file_upgrades_and_keeps_every_row() -> None:
    connection = _legacy_events_connection()
    assert current_version(connection) == 0

    migrate(connection, MIGRATIONS)

    assert current_version(connection) == CURRENT_VERSION
    rows = connection.execute("SELECT event_id, workspace_id, device_id FROM events").fetchall()
    assert len(rows) == 2
    assert all(row[0] for row in rows), "every legacy row must get an event_id"
    assert [row[1] for row in rows] == ["local", "local"]
    assert [row[2] for row in rows] == ["local", "local"]


def test_intent_store_upgrades_a_legacy_file_and_records_the_version(tmp_path) -> None:
    db = tmp_path / "odi.db"
    legacy = sqlite3.connect(db)
    legacy.execute(
        """
        CREATE TABLE events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            event_type TEXT NOT NULL,
            payload TEXT NOT NULL
        )
        """
    )
    legacy.execute(
        "INSERT INTO events (timestamp, event_type, payload) "
        "VALUES ('2026-01-01T00:00:00', 'JOB_CREATED', '{\"id\": \"j1\"}')"
    )
    legacy.commit()
    legacy.close()

    store = IntentStore(str(db))
    try:
        assert len(store.get_stream()) == 1
    finally:
        store.close()

    check = sqlite3.connect(db)
    try:
        assert current_version(check) == CURRENT_VERSION
    finally:
        check.close()


def test_intent_store_opens_a_current_database_as_a_no_op(tmp_path) -> None:
    db = tmp_path / "odi.db"
    store = IntentStore(str(db))
    store.append("JOB_CREATED", {"id": "j1"})
    store.close()

    check = sqlite3.connect(db)
    try:
        assert current_version(check) == CURRENT_VERSION
    finally:
        check.close()

    reopened = IntentStore(str(db))
    try:
        assert [event["type"] for event in reopened.get_stream()] == ["JOB_CREATED"]
    finally:
        reopened.close()


def test_a_gap_in_the_registry_names_the_missing_version() -> None:
    ladder = (
        Migration(1, "first", lambda conn: None),
        Migration(3, "third", lambda conn: None),
    )

    with pytest.raises(MigrationError, match="No migration registered for version 2"):
        migration_steps(ladder, 0, 3)


def test_migration_steps_returns_only_newer_steps_in_order() -> None:
    ladder = tuple(Migration(n, f"step {n}", lambda conn: None) for n in (1, 2, 3))

    assert [step.version for step in migration_steps(ladder, 0, 3)] == [1, 2, 3]
    assert [step.version for step in migration_steps(ladder, 2, 3)] == [3]
    assert migration_steps(ladder, 3, 3) == ()


def test_a_failing_step_rolls_back_and_leaves_the_version_alone() -> None:
    def explode(connection: sqlite3.Connection) -> None:
        connection.execute("CREATE TABLE half_done (a INTEGER)")
        raise sqlite3.OperationalError("boom")

    ladder = (
        Migration(1, "first", lambda conn: None),
        Migration(2, "explodes", explode),
    )
    connection = sqlite3.connect(":memory:")
    connection.execute("CREATE TABLE events (id INTEGER PRIMARY KEY AUTOINCREMENT)")

    with pytest.raises(MigrationError, match="migration 2"):
        migrate(connection, ladder, label="test store")

    assert current_version(connection) == 0
    tables = {
        row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert "half_done" not in tables, "a failed step must not leave a partial schema"


def test_migrate_runs_inside_an_enclosing_transaction() -> None:
    """Both stores call the runner while their own open still holds a write.

    ``IntentStore._init_db`` and ``StudioMemory.__init__`` both do their create
    work inside ``with connection:``, so the runner must tolerate a transaction
    that is already open rather than raising "cannot start a transaction within
    a transaction".
    """
    connection = sqlite3.connect(":memory:")
    connection.execute("CREATE TABLE events (id INTEGER PRIMARY KEY AUTOINCREMENT)")
    connection.execute("BEGIN IMMEDIATE")

    assert migrate(connection, MIGRATIONS) == CURRENT_VERSION
    assert connection.in_transaction, "the enclosing transaction must still be open"
    connection.commit()
    assert current_version(connection) == CURRENT_VERSION


def test_a_failing_step_inside_an_enclosing_transaction_rolls_back_to_the_savepoint() -> None:
    def explode(connection: sqlite3.Connection) -> None:
        connection.execute("CREATE TABLE half_done (a INTEGER)")
        raise sqlite3.OperationalError("boom")

    ladder = (
        Migration(1, "first", lambda conn: None),
        Migration(2, "explodes", explode),
    )
    connection = sqlite3.connect(":memory:")
    connection.execute("CREATE TABLE events (id INTEGER PRIMARY KEY AUTOINCREMENT)")
    connection.execute("BEGIN IMMEDIATE")
    connection.execute("CREATE TABLE kept (a INTEGER)")

    with pytest.raises(MigrationError):
        migrate(connection, ladder, label="test store")

    tables = {
        row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert "half_done" not in tables
    assert "kept" in tables, "the enclosing transaction must survive the failed ladder"
    assert current_version(connection) == 0
    connection.commit()
