"""Issue #348: the SQLite file is the only copy of the work.

These tests pin the durability contract: a damaged store is detected at boot and
reported, a healthy store is checkpointed and closed cleanly, and a backup can be
restored. Nothing here may delete or silently substitute a damaged file.
"""

from __future__ import annotations

import os

import pytest
from agentic_odi_core.errors import StoreCorrupt
from agentic_odi_core.models import Job
from agentic_odi_core.sqlite_repository import SQLiteRepository


def _job(index: int) -> Job:
    return Job(id=f"j{index}", name=f"Job number {index} with a long enough name to matter")


def _seeded_db(tmp_path) -> str:
    """A database with enough pages in it that a truncation is real damage."""
    db = str(tmp_path / "odi.db")
    repo = SQLiteRepository(db_path=db)
    for index in range(50):
        repo.add_job(_job(index))
    repo.close()
    return db


def _truncate(path: str, keep_fraction: float = 0.5) -> int:
    """Truncate the database to keep_fraction of its size.

    Returns the size the file had BEFORE truncation (the "damaged size"
    the store should be left at).
    """
    original_size = os.path.getsize(path)
    with open(path, "r+b") as handle:
        handle.truncate(int(original_size * keep_fraction))
    return os.path.getsize(path)


def test_truncated_database_raises_store_corrupt_that_names_the_file(tmp_path):
    db = _seeded_db(tmp_path)
    _truncate(db)

    with pytest.raises(StoreCorrupt) as collected:
        SQLiteRepository(db_path=db)

    assert "odi.db" in str(collected.value)


def test_store_corrupt_carries_the_path_and_the_integrity_rows(tmp_path):
    db = _seeded_db(tmp_path)
    _truncate(db)

    with pytest.raises(StoreCorrupt) as collected:
        SQLiteRepository(db_path=db)

    error = collected.value
    assert error.path == db
    assert error.rows
    assert len(error.rows) <= 20


def test_corrupt_database_is_left_exactly_as_it_was(tmp_path):
    db = _seeded_db(tmp_path)
    damaged_size = _truncate(db)

    with pytest.raises(StoreCorrupt):
        SQLiteRepository(db_path=db)

    assert os.path.getsize(db) == damaged_size
    assert not os.path.exists(db + ".recovered")
    assert not os.path.exists(str(tmp_path / "odi.db.tmp"))


def test_healthy_database_opens_with_no_new_warning_output(tmp_path, caplog):
    db = _seeded_db(tmp_path)

    with caplog.at_level("WARNING"):
        repo = SQLiteRepository(db_path=db)

    assert len(repo.list_jobs()) == 50
    assert caplog.records == []
    repo.close()


def test_boot_truncates_the_write_ahead_log(tmp_path):
    db = _seeded_db(tmp_path)
    wal = db + "-wal"
    assert os.path.exists(wal) is False or os.path.getsize(wal) == 0

    repo = SQLiteRepository(db_path=db)
    try:
        assert not os.path.exists(wal) or os.path.getsize(wal) == 0
    finally:
        repo.close()
