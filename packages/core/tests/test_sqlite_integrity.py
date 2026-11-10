"""Tests for the boot integrity gate and clean shutdown (issue #598).

The database is the only copy, so the store must gate its own boot: a damaged
file has to fail with a message a person can act on, and a clean stop has to
leave no write-ahead log behind for the next process to recover. These tests
drive the real SQLite files, not mocks, because the failure mode is the file
format itself.
"""

from __future__ import annotations

import os
import sqlite3
import time

import pytest
from agentic_odi_core.errors import StoreCorrupt, error_status
from agentic_odi_core.integrity import (
    BOOT_CHECK_VM_BUDGET,
    check_integrity,
    ensure_intact,
)
from agentic_odi_core.intent_store import IntentStore
from agentic_odi_core.recovery import (
    backup_prefix,
    corrupt_store_message,
    format_backup_time,
    latest_backup,
)
from agentic_odi_core.repository import InMemoryRepository
from agentic_odi_core.sqlite_repository import SQLiteRepository

#: Rows in the "50k-row fixture" the issue names. The gate reads a bounded
#: number of pages, so the bound is independent of this; the test exists to
#: prove that on the size the issue calls out.
FIXTURE_ROWS = 50_000


def _write_events(store: IntentStore, rows: int) -> None:
    with store.conn:
        store.conn.executemany(
            "INSERT INTO events "
            "(event_id, workspace_id, device_id, timestamp, event_type, payload) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [
                (
                    f"e{i}",
                    "local",
                    "local",
                    "2026-01-01T00:00:00",
                    "JOB_CREATED",
                    f'{{"id": "j{i % 30}", "name": "Job {i}"}}',
                )
                for i in range(rows)
            ],
        )


def _corrupt_page(path: str) -> None:
    """Overwrite one page in the middle of the file, past the header."""
    with open(path, "r+b") as handle:
        handle.seek(4096 * 2)
        handle.write(b"\xde\xad\xbe\xef" * 1024)


def _build_corrupt_store(tmp_path, rows: int = 2_000) -> str:
    db_path = str(tmp_path / "odi.db")
    store = IntentStore(db_path)
    try:
        _write_events(store, rows)
    finally:
        store.close()
    _corrupt_page(db_path)
    return db_path


# -- the check itself ------------------------------------------------------


def test_a_healthy_file_passes_the_check(tmp_path) -> None:
    db_path = str(tmp_path / "odi.db")
    store = IntentStore(db_path)
    try:
        _write_events(store, 100)
    finally:
        store.close()

    connection = sqlite3.connect(db_path)
    try:
        result = check_integrity(connection)
    finally:
        connection.close()

    assert result.ok
    assert result.status == "ok"
    assert result.problems == []


def test_a_corrupt_page_is_reported_not_raised_by_the_check(tmp_path) -> None:
    db_path = _build_corrupt_store(tmp_path)

    connection = sqlite3.connect(db_path)
    try:
        result = check_integrity(connection)
    finally:
        connection.close()

    assert result.status == "corrupt"
    assert result.problems


def test_a_file_that_is_not_a_database_is_corrupt_not_a_crash(tmp_path) -> None:
    path = tmp_path / "not-a-db.db"
    path.write_text("this is plainly not a SQLite file")

    connection = sqlite3.connect(str(path))
    try:
        result = check_integrity(connection)
    finally:
        connection.close()

    assert result.status == "corrupt"
    assert any("not a database" in problem for problem in result.problems)


def test_the_check_is_bounded_and_defers_rather_than_scanning(tmp_path) -> None:
    """A spent budget reports ``deferred``; it never scans the whole file."""
    db_path = str(tmp_path / "odi.db")
    store = IntentStore(db_path)
    try:
        _write_events(store, 5_000)
    finally:
        store.close()

    connection = sqlite3.connect(db_path)
    try:
        # A one-opcode budget cannot finish even a small check, so the result
        # must be ``deferred`` and the call must return promptly.
        started = time.perf_counter()
        result = check_integrity(connection, budget=1)
        elapsed = time.perf_counter() - started
    finally:
        connection.close()

    assert result.status == "deferred"
    assert elapsed < 1.0


def test_the_default_budget_covers_the_reference_fixture(tmp_path) -> None:
    """The documented bound must fully check the size the issue calls out."""
    db_path = str(tmp_path / "odi.db")
    store = IntentStore(db_path)
    try:
        _write_events(store, FIXTURE_ROWS)
    finally:
        store.close()

    connection = sqlite3.connect(db_path)
    try:
        result = check_integrity(connection)
    finally:
        connection.close()

    # 50k rows costs well under a tenth of the budget, so a healthy store of
    # this size is always checked in full rather than deferred.
    assert result.status == "ok"
    assert BOOT_CHECK_VM_BUDGET >= 5_000_000


# -- the gate on open ------------------------------------------------------


def test_ensure_intact_raises_a_message_that_names_the_file(tmp_path) -> None:
    db_path = _build_corrupt_store(tmp_path)

    connection = sqlite3.connect(db_path)
    try:
        with pytest.raises(StoreCorrupt) as raised:
            ensure_intact(connection, db_path, label="Your database")
    finally:
        connection.close()

    assert raised.value.path == db_path
    assert db_path in str(raised.value)
    assert raised.value.problems


def test_opening_a_corrupt_store_raises_store_corrupt(tmp_path) -> None:
    db_path = _build_corrupt_store(tmp_path)

    with pytest.raises(StoreCorrupt) as raised:
        IntentStore(db_path)

    assert raised.value.path == db_path
    assert "integrity check" in str(raised.value)


def test_a_failed_check_never_touches_the_file(tmp_path) -> None:
    """The guardrail: a damaged file is left exactly as it was found."""
    db_path = _build_corrupt_store(tmp_path)
    before = os.stat(db_path)
    with open(db_path, "rb") as handle:
        original = handle.read()

    with pytest.raises(StoreCorrupt):
        IntentStore(db_path)

    after = os.stat(db_path)
    with open(db_path, "rb") as handle:
        assert handle.read() == original
    assert (after.st_size, after.st_mtime_ns) == (before.st_size, before.st_mtime_ns)
    # No sidecar was created beside the damaged file either.
    assert not os.path.exists(db_path + "-wal")


def test_a_corrupt_store_fails_the_repository_open_too(tmp_path) -> None:
    db_path = _build_corrupt_store(tmp_path)

    with pytest.raises(StoreCorrupt):
        SQLiteRepository(db_path)


def test_store_corrupt_maps_to_a_server_error() -> None:
    assert error_status(StoreCorrupt("/tmp/odi.db")) == 500


# -- clean shutdown --------------------------------------------------------


def test_close_checkpoints_and_leaves_no_wal_sidecar(tmp_path) -> None:
    db_path = tmp_path / "odi.db"
    store = IntentStore(str(db_path))
    _write_events(store, 5_000)
    assert (tmp_path / "odi.db-wal").exists()

    store.close()

    assert db_path.exists()
    assert list(tmp_path.glob("odi.db-wal")) == []
    assert list(tmp_path.glob("odi.db-shm")) == []


def test_the_wal_does_not_grow_after_a_clean_shutdown(tmp_path) -> None:
    """The regression the issue names: a clean stop leaves no growing log."""
    db_path = tmp_path / "odi.db"
    store = IntentStore(str(db_path))
    _write_events(store, 5_000)
    wal_path = tmp_path / "odi.db-wal"
    assert wal_path.exists()

    store.close()

    # Nothing is left for a later process to recover or to keep growing.
    assert not wal_path.exists()

    # Reopen and close once more: the second clean stop is just as clean.
    reopened = IntentStore(str(db_path))
    reopened.close()
    assert not wal_path.exists()
    assert list(tmp_path.glob("odi.db-shm")) == []


def test_checkpoint_is_safe_after_close_and_on_a_memory_store(tmp_path) -> None:
    store = IntentStore(str(tmp_path / "odi.db"))
    store.close()
    store.close()  # idempotent
    store.checkpoint("PASSIVE")  # must not raise on a closed store

    memory = IntentStore(":memory:")
    try:
        memory.checkpoint("PASSIVE")
    finally:
        memory.close()


def test_a_healthy_boot_is_bounded_on_the_reference_fixture(tmp_path) -> None:
    """A healthy 50k-row file must pass the gate well inside 200ms.

    The budget covers a full check of this fixture, so the assertion is on the
    gate's cost, not on the whole repository replay.
    """
    db_path = str(tmp_path / "odi.db")
    store = IntentStore(db_path)
    try:
        _write_events(store, FIXTURE_ROWS)
    finally:
        store.close()

    samples: list[float] = []
    for _ in range(3):
        started = time.perf_counter()
        reopened = IntentStore(db_path)
        samples.append(time.perf_counter() - started)
        reopened.close()

    median = sorted(samples)[len(samples) // 2]
    assert median < 0.2, f"boot gate median {median:.3f}s"
    assert reopened.integrity.status == "ok"


# -- repository parity -----------------------------------------------------


def test_in_memory_repository_reports_intact_and_checkpoints_as_a_noop() -> None:
    repo = InMemoryRepository()

    assert repo.integrity == "ok"
    repo.checkpoint("PASSIVE")
    repo.close()


def test_sqlite_repository_exposes_the_boot_integrity_result(tmp_path) -> None:
    repo = SQLiteRepository(str(tmp_path / "odi.db"))
    try:
        assert repo.integrity == "ok"
        repo.checkpoint("PASSIVE")
    finally:
        repo.close()


# -- the recovery message --------------------------------------------------


def test_backup_prefix_groups_a_database_with_its_history() -> None:
    assert backup_prefix("/home/me/.agentic-odi/odi.db") == "odi"
    assert backup_prefix("/home/me/.agentic-odi/studio.db") == "studio"
    assert backup_prefix("/tmp/renamed.db") == "renamed"


def test_latest_backup_returns_the_newest_by_timestamp(tmp_path) -> None:
    backups = tmp_path / "backups"
    backups.mkdir()
    (backups / "odi-20260101T060000Z.db").write_bytes(b"old")
    (backups / "odi-20260102T061400Z.db").write_bytes(b"new")
    (backups / "studio-20260103T000000Z.db").write_bytes(b"other")

    found = latest_backup("/home/me/.agentic-odi/odi.db", directory=backups)

    assert found is not None
    assert found.name == "odi-20260102T061400Z.db"


def test_latest_backup_is_none_when_nothing_exists(tmp_path) -> None:
    assert latest_backup("/home/me/.agentic-odi/odi.db", directory=tmp_path / "nope") is None


def test_backup_time_is_read_from_the_filename(tmp_path) -> None:
    assert format_backup_time(tmp_path / "odi-20260102T061400Z.db") == "06:14"
    # An unexpected name is shown as-is rather than dropped.
    assert format_backup_time(tmp_path / "odi-latest.db") == "odi-latest.db"


def test_the_message_names_the_file_and_the_last_backup(tmp_path) -> None:
    backups = tmp_path / "backups"
    backups.mkdir()
    backup = backups / "odi-20260102T061400Z.db"
    backup.write_bytes(b"good")
    error = StoreCorrupt(str(tmp_path / "odi.db"), ["database disk image is malformed"])

    message = corrupt_store_message(error, backup=backup)

    assert str(tmp_path / "odi.db") in message
    assert "06:14" in message
    assert backup.name in message
    assert "left untouched" in message


def test_the_message_is_actionable_when_no_backup_exists(tmp_path) -> None:
    error = StoreCorrupt(str(tmp_path / "odi.db"), ["database disk image is malformed"])

    message = corrupt_store_message(error, backup=None)

    assert "No backup exists yet." in message
    assert str(tmp_path / "odi.db") in message
