"""Bounded retention for backups (issue #1163).

`backup_database` writes a new verified snapshot every time it is called and
nothing ever removed one, so the backups directory grows until it is itself the
disk-full failure the write path is supposed to survive. These tests pin the
pruning behaviour added to keep the directory bounded.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from agentic_odi_core.recovery import (
    BACKUP_KEEP_ENV,
    DEFAULT_BACKUP_KEEP,
    backup_database,
    prune_backups,
)


def _make_backup(folder: Path, stamp: str, when: datetime) -> Path:
    """Write a backup file whose name and mtime both encode ``when``."""
    path = folder / f"odi-{stamp}.db"
    path.write_bytes(b"SQLite format 3\x00")
    epoch = when.timestamp()
    os.utime(path, (epoch, epoch))
    return path


def _stamp(when: datetime) -> str:
    return when.strftime("%Y%m%dT%H%M%SZ")


def _source_db(tmp_path: Path) -> Path:
    source = tmp_path / "odi.db"
    conn = sqlite3.connect(str(source))
    try:
        conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
        conn.commit()
    finally:
        conn.close()
    return source


def test_prune_keeps_the_newest_n(tmp_path):
    folder = tmp_path / "backups"
    folder.mkdir()
    base = datetime(2026, 11, 5, 10, 0, 0, tzinfo=timezone.utc)
    paths = [
        _make_backup(folder, _stamp(base + timedelta(seconds=i)), base + timedelta(seconds=i))
        for i in range(20)
    ]
    removed = prune_backups("odi.db", directory=folder, keep=5)

    remaining = sorted(folder.glob("odi-*.db"))
    assert len(remaining) == 5
    assert [p.name for p in remaining] == [p.name for p in paths[-5:]]
    assert len(removed) == 15
    assert {p.name for p in removed} == {p.name for p in paths[:15]}


def test_prune_never_deletes_one_per_day_for_a_week(tmp_path):
    folder = tmp_path / "backups"
    folder.mkdir()
    # 10 distinct days, 3 backups each, newest day first.
    days = [datetime(2026, 11, 10 - i, 10, 0, 0, tzinfo=timezone.utc) for i in range(10)]
    for day in days:
        for j in range(3):
            _make_backup(folder, _stamp(day + timedelta(seconds=j)), day + timedelta(seconds=j))

    prune_backups("odi.db", directory=folder, keep=2)
    remaining = {p.name for p in folder.glob("odi-*.db")}

    # Keep the newest two (both on the newest day).
    assert f"odi-{_stamp(days[0] + timedelta(seconds=2))}.db" in remaining
    assert f"odi-{_stamp(days[0] + timedelta(seconds=1))}.db" in remaining
    # One newest survivor per calendar day for the last 7 distinct days.
    for i in range(7):
        assert f"odi-{_stamp(days[i] + timedelta(seconds=2))}.db" in remaining
    # An older day's newest is neither kept nor day-protected: deleted.
    assert f"odi-{_stamp(days[7] + timedelta(seconds=2))}.db" not in remaining
    assert len(remaining) == 8


def test_prune_does_not_delete_the_backup_it_just_wrote(tmp_path):
    source = _source_db(tmp_path)
    folder = tmp_path / "backups"
    dest = backup_database(str(source), directory=folder)
    assert dest.exists()

    # Pruning again with a tiny keep must not remove the backup just written.
    prune_backups(str(source), directory=folder, keep=1)
    assert dest.exists()


def test_a_zero_keep_falls_back_to_the_default(tmp_path, monkeypatch):
    monkeypatch.setenv(BACKUP_KEEP_ENV, "0")
    folder = tmp_path / "backups"
    folder.mkdir()
    base = datetime(2026, 11, 5, 10, 0, 0, tzinfo=timezone.utc)
    paths = [
        _make_backup(folder, _stamp(base + timedelta(seconds=i)), base + timedelta(seconds=i))
        for i in range(20)
    ]
    removed = prune_backups("odi.db", directory=folder)

    remaining = sorted(folder.glob("odi-*.db"))
    # A non-positive keep is refused and falls back to the default (14).
    assert len(remaining) == DEFAULT_BACKUP_KEEP
    assert len(removed) == 20 - DEFAULT_BACKUP_KEEP
    assert [p.name for p in remaining] == [p.name for p in paths[20 - DEFAULT_BACKUP_KEEP :]]
    assert {p.name for p in removed} == {p.name for p in paths[: 20 - DEFAULT_BACKUP_KEEP]}


def test_a_failed_unlink_does_not_raise(tmp_path, monkeypatch):
    folder = tmp_path / "backups"
    folder.mkdir()
    base = datetime(2026, 11, 5, 10, 0, 0, tzinfo=timezone.utc)
    for i in range(5):
        _make_backup(folder, _stamp(base + timedelta(seconds=i)), base + timedelta(seconds=i))

    def _boom(self: Path) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(Path, "unlink", _boom)
    removed = prune_backups("odi.db", directory=folder, keep=1)

    assert removed == []
    # Nothing was deleted despite the failing unlink.
    assert len(list(folder.glob("odi-*.db"))) == 5
