"""Tests for backup and restore (issue #1133).

The restore must delete stale WAL/SHM/journal sidecars, verify the restored
file, and leave a recoverable pre-restore copy. These tests drive real SQLite
files because the failure mode is the file format itself.
"""

from __future__ import annotations

import os
import sqlite3
import stat
from pathlib import Path

import pytest
from agentic_odi_core.recovery import (
    _integrity_ok,
    backup_database,
    restore_database,
)


def _make_database(path: Path) -> None:
    conn = sqlite3.connect(str(path))
    try:
        conn.execute("CREATE TABLE t (x INTEGER)")
        conn.execute("INSERT INTO t VALUES (1)")
        conn.commit()
    finally:
        conn.close()


def _rows(path: Path) -> list[tuple[int]]:
    conn = sqlite3.connect(str(path))
    try:
        return conn.execute("SELECT x FROM t").fetchall()
    finally:
        conn.close()


def _create_stale_wal_files(path: Path) -> None:
    """Create stale WAL/SHM files by opening in WAL mode, writing, and closing without checkpoint."""
    conn = sqlite3.connect(str(path))
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA wal_autocheckpoint=0")
        conn.execute("INSERT INTO t VALUES (2)")
        conn.commit()
    finally:
        conn.close()
    # Manually create WAL/SHM files to simulate a crash (SQLite cleans up on clean close).
    # The -shm file is a shared memory file, typically 32KB of zeros.
    wal_path = path.parent / f"{path.name}-wal"
    shm_path = path.parent / f"{path.name}-shm"
    wal_path.write_bytes(b"\x00" * 1024)  # Minimal WAL header
    shm_path.write_bytes(b"\x00" * 32768)  # 32KB SHM file
    assert wal_path.exists()
    assert shm_path.exists()


def test_restore_removes_stale_wal_and_shm(tmp_path: Path) -> None:
    """After a restore, no -wal, -shm, or -journal file remains beside the database."""
    db = tmp_path / "odi.db"
    _make_database(db)
    backup = backup_database(str(db), directory=tmp_path / "backups")

    # Create stale WAL/SHM files (simulating a crashed session).
    _create_stale_wal_files(db)
    assert (tmp_path / "odi.db-wal").exists()
    assert (tmp_path / "odi.db-shm").exists()

    # Restore the backup.
    restore_database(backup, str(db))

    # Sidecars must be gone.
    assert not (tmp_path / "odi.db-wal").exists()
    assert not (tmp_path / "odi.db-shm").exists()
    assert not (tmp_path / "odi.db-journal").exists()
    # Data must match the backup.
    assert _rows(db) == [(1,)]


def test_restore_leaves_a_pre_restore_copy(tmp_path: Path) -> None:
    """The damaged state is preserved as .pre-restore (plus sidecars if they existed)."""
    db = tmp_path / "odi.db"
    _make_database(db)
    backup = backup_database(str(db), directory=tmp_path / "backups")

    # Create stale WAL/SHM files (simulating a crashed session).
    _create_stale_wal_files(db)
    wal_before = (tmp_path / "odi.db-wal").read_bytes()
    shm_before = (tmp_path / "odi.db-shm").read_bytes()

    # Restore the backup.
    safety = restore_database(backup, str(db))

    # The pre-restore file and its sidecars must exist.
    assert safety.name == "odi.db.pre-restore"
    assert safety.exists()
    assert (tmp_path / "odi.db.pre-restore-wal").exists()
    assert (tmp_path / "odi.db.pre-restore-shm").exists()
    # The pre-restore sidecars must match the originals.
    assert (tmp_path / "odi.db.pre-restore-wal").read_bytes() == wal_before
    assert (tmp_path / "odi.db.pre-restore-shm").read_bytes() == shm_before
    # The pre-restore database must have the modified data.
    assert _rows(safety) == [(1,), (2,)]


def test_restore_refuses_a_corrupt_backup(tmp_path: Path) -> None:
    """Existing behaviour guard: a corrupt backup is refused and nothing changes."""
    db = tmp_path / "odi.db"
    _make_database(db)
    broken = tmp_path / "odi-20260101T000000Z.db"
    broken.write_bytes(b"not a database")

    with pytest.raises(ValueError, match="integrity check"):
        restore_database(broken, str(db))

    # The live file is untouched and no safety copy was written.
    assert _rows(db) == [(1,)]
    assert not (tmp_path / "odi.db.pre-restore").exists()


def test_restore_is_verified_after_the_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed post-copy verification leaves the original in place and raises."""
    db = tmp_path / "odi.db"
    _make_database(db)
    backup = backup_database(str(db), directory=tmp_path / "backups")

    # Create stale WAL/SHM files.
    _create_stale_wal_files(db)
    original_rows = _rows(db)
    original_wal = (
        (tmp_path / "odi.db-wal").read_bytes() if (tmp_path / "odi.db-wal").exists() else None
    )
    original_shm = (
        (tmp_path / "odi.db-shm").read_bytes() if (tmp_path / "odi.db-shm").exists() else None
    )

    # Make the integrity check fail on the second call (the post-copy verification).
    call_count = 0

    def failing_integrity_ok(path: Path) -> bool:
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            return False
        return _integrity_ok(path)

    monkeypatch.setattr("agentic_odi_core.recovery._integrity_ok", failing_integrity_ok)

    with pytest.raises(RuntimeError, match="restored copy failed its integrity check"):
        restore_database(backup, str(db))

    # The original database and sidecars must be restored.
    assert _rows(db) == original_rows
    if original_wal is not None:
        assert (tmp_path / "odi.db-wal").exists()
        assert (tmp_path / "odi.db-wal").read_bytes() == original_wal
    if original_shm is not None:
        assert (tmp_path / "odi.db-shm").exists()
        assert (tmp_path / "odi.db-shm").read_bytes() == original_shm
    # The pre-restore copy should still exist.
    assert (tmp_path / "odi.db.pre-restore").exists()


def test_restore_preserves_file_mode(tmp_path: Path) -> None:
    """The destination file mode is preserved across the restore."""
    db = tmp_path / "odi.db"
    _make_database(db)
    backup = backup_database(str(db), directory=tmp_path / "backups")

    # Set a specific mode on the live database.
    os.chmod(db, 0o640)
    original_mode = stat.S_IMODE(db.stat().st_mode)

    # Restore the backup.
    restore_database(backup, str(db))

    # The mode must be preserved.
    restored_mode = stat.S_IMODE(db.stat().st_mode)
    assert restored_mode == original_mode


def test_restore_handles_journal_file(tmp_path: Path) -> None:
    """A -journal file (rollback mode) is also removed and preserved."""
    db = tmp_path / "odi.db"
    _make_database(db)
    backup = backup_database(str(db), directory=tmp_path / "backups")

    # Create a journal file by forcing rollback mode and interrupting a transaction.
    conn = sqlite3.connect(str(db))
    try:
        conn.execute("PRAGMA journal_mode=DELETE")
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("INSERT INTO t VALUES (3)")
        # Do not commit, leave the journal file.
    finally:
        conn.close()

    # In DELETE mode, the journal file is created during the transaction
    # but may be removed on rollback. Let's create it manually to simulate
    # a stale journal file.
    journal_path = tmp_path / "odi.db-journal"
    journal_path.write_bytes(b"stale journal content")

    assert journal_path.exists()

    # Restore the backup.
    restore_database(backup, str(db))

    # Journal file must be gone from live, preserved in pre-restore.
    assert not journal_path.exists()
    assert (tmp_path / "odi.db.pre-restore-journal").exists()
    assert (tmp_path / "odi.db.pre-restore-journal").read_bytes() == b"stale journal content"
    # Data must match the backup.
    assert _rows(db) == [(1,)]


def test_restore_works_when_no_sidecars_exist(tmp_path: Path) -> None:
    """Restore succeeds normally when no WAL/SHM/journal files are present."""
    db = tmp_path / "odi.db"
    _make_database(db)
    backup = backup_database(str(db), directory=tmp_path / "backups")

    # Ensure no sidecars exist.
    assert not (tmp_path / "odi.db-wal").exists()
    assert not (tmp_path / "odi.db-shm").exists()
    assert not (tmp_path / "odi.db-journal").exists()

    # Restore the backup.
    safety = restore_database(backup, str(db))

    # No sidecars should be created.
    assert not (tmp_path / "odi.db-wal").exists()
    assert not (tmp_path / "odi.db-shm").exists()
    assert not (tmp_path / "odi.db-journal").exists()
    # Pre-restore copy exists without sidecars.
    assert safety.exists()
    assert not (tmp_path / "odi.db.pre-restore-wal").exists()
    assert not (tmp_path / "odi.db.pre-restore-shm").exists()
    assert not (tmp_path / "odi.db.pre-restore-journal").exists()
    # Data matches backup.
    assert _rows(db) == [(1,)]


def test_restore_signature_accepts_path_objects(tmp_path: Path) -> None:
    """The function signature accepts Path objects for backup_path."""
    db = tmp_path / "odi.db"
    _make_database(db)
    backup = backup_database(str(db), directory=tmp_path / "backups")

    # Call with Path object for backup_path.
    safety = restore_database(backup, str(db))

    assert safety.exists()
    assert _rows(db) == [(1,)]
