"""Read-side helpers for a store that failed its integrity check.

The boot gate raises :class:`~agentic_odi_core.errors.StoreCorrupt`; this module
turns that into the one sentence a person can act on: which file is damaged,
when the last good copy was taken, and what to run to put it back.

Creating, rotating, and restoring backups is the next slice (#599). This module
only *finds* an existing backup so the failure message can name it, and stays
correct when none exists yet.
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import stat
from datetime import date, datetime, timezone
from pathlib import Path

from agentic_odi_core.errors import StoreCorrupt

#: Where backups live. Beside the database, so a person who moves the database
#: moves its history with it and a restore does not depend on a platform path.
DEFAULT_BACKUP_DIR = "~/.agentic-odi/backups"

BACKUP_DIR_ENV = "AGENTIC_ODI_BACKUP_DIR"

#: How many snapshots a database keeps unless told otherwise.
DEFAULT_BACKUP_KEEP = 14

#: Overrides the number of snapshots kept after a successful backup.
BACKUP_KEEP_ENV = "AGENTIC_ODI_BACKUP_KEEP"

#: How many distinct calendar days keep their newest snapshot regardless of count.
BACKUP_DAILY_DAYS = 7

#: The prefix a database's backups share, keyed by the database file's stem.
_BACKUP_PREFIXES = {"odi": "odi", "studio": "studio"}


def backups_dir() -> Path:
    """Resolve the directory backups are written to."""
    configured = os.environ.get(BACKUP_DIR_ENV)
    if configured:
        return Path(configured).expanduser()
    return Path(DEFAULT_BACKUP_DIR).expanduser()


def backup_prefix(db_path: str) -> str:
    """The backup filename prefix for a database path.

    ``~/.agentic-odi/odi.db`` backs up as ``odi-<UTC>.db``; anything else uses
    its own stem so a renamed database still groups with its history.
    """
    stem = Path(db_path).stem or "odi"
    return _BACKUP_PREFIXES.get(stem, stem)


def _backups_newest_first(db_path: str, folder: Path) -> list[Path]:
    """Every backup of ``db_path`` under ``folder``, newest first.

    Newest is by modification time, with the filename as a tiebreaker. The
    filename stamp has one-second resolution, so a pair written in the same
    second differ only by their collision suffix and the clock cannot order
    them; the file's own mtime can.
    """
    if not folder.is_dir():
        return []
    prefix = backup_prefix(db_path)
    candidates = [path for path in folder.glob(f"{prefix}-*.db") if path.is_file()]
    return sorted(candidates, key=lambda path: (path.stat().st_mtime_ns, path.name), reverse=True)


def latest_backup(db_path: str, *, directory: Path | None = None) -> Path | None:
    """Return the newest existing backup for a database, or ``None``."""
    folder = directory if directory is not None else backups_dir()
    ordered = _backups_newest_first(db_path, folder)
    return ordered[0] if ordered else None


def _keep_count() -> int:
    """The configured snapshot count, falling back to the default.

    A keep count of zero would delete the snapshot the backup just wrote, so a
    non-numeric or non-positive value is refused rather than obeyed.
    """
    raw = os.environ.get(BACKUP_KEEP_ENV)
    if raw is None or not raw.strip():
        return DEFAULT_BACKUP_KEEP
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_BACKUP_KEEP
    return value if value > 0 else DEFAULT_BACKUP_KEEP


def prune_backups(
    db_path: str,
    *,
    keep: int | None = None,
    directory: Path | None = None,
    now: datetime | None = None,
) -> list[Path]:
    """Delete old backups for ``db_path``, returning the paths removed.

    The newest ``keep`` snapshots survive, plus the newest snapshot of each of
    the last :data:`BACKUP_DAILY_DAYS` distinct calendar days — so a burst of
    backups in one afternoon cannot erase the one from last Tuesday. A failed
    unlink is skipped, never raised: a backup directory that cannot be pruned is
    still a backup directory that works.
    """
    folder = directory if directory is not None else backups_dir()
    limit = _keep_count() if keep is None else keep
    if limit <= 0:
        limit = DEFAULT_BACKUP_KEEP
    ordered = _backups_newest_first(db_path, folder)
    if not ordered:
        return []

    today = (now or datetime.now(timezone.utc)).astimezone().date()
    kept = set(ordered[:limit])
    days_seen: set[date] = set()
    for path in ordered:
        if len(days_seen) >= BACKUP_DAILY_DAYS:
            break
        # A snapshot older than the newest ``keep`` is still worth a day slot
        # only while it belongs to one of the last seven days.
        day = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).astimezone().date()
        if (today - day).days >= BACKUP_DAILY_DAYS:
            break
        if day in days_seen:
            continue
        days_seen.add(day)
        kept.add(path)

    removed: list[Path] = []
    for path in ordered:
        if path in kept:
            continue
        try:
            path.unlink()
        except OSError:
            continue
        removed.append(path)
    return removed


def format_backup_time(backup: Path) -> str:
    """Read the UTC time out of a backup filename, as local ``HH:MM``.

    The filename stamp is UTC by construction; the message sits beside the
    reader's clock, so it is converted for display rather than shown raw.
    """
    stem = backup.stem
    _, _, stamp = stem.partition("-")
    # A backup taken in a second that already has one gains a ``-N`` suffix so
    # the pair are two files. The suffix is not part of the timestamp.
    head, sep, tail = stamp.rpartition("-")
    if sep and tail.isdigit():
        stamp = head
    try:
        parsed = datetime.strptime(stamp, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return backup.name
    return parsed.astimezone().strftime("%H:%M")


def corrupt_store_message(error: StoreCorrupt, *, backup: Path | None = None) -> str:
    """One actionable sentence naming the damaged file and the last good copy.

    This is the message the boot failure page and the terminal both show. It
    never claims a restore happened, and it never offers to touch the file: the
    file is left untouched until the person chooses.
    """
    resolved = backup if backup is not None else latest_backup(error.path)
    if resolved is None:
        backup_line = "No backup exists yet."
    else:
        backup_line = f"Last backup: {format_backup_time(resolved)} local ({resolved.name})."
    return (
        f"{error.label} failed its integrity check: {error.path}. "
        f"{backup_line} The file has been left untouched — restore a backup before opening it again."
    )


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _integrity_ok(path: Path) -> bool:
    """True when SQLite can open ``path`` and its integrity check passes.

    A missing file is not a valid database: SQLite would otherwise create an
    empty one and report ``ok``, which would let a restore clobber the live
    store with nothing.
    """
    if not path.is_file():
        return False
    conn = sqlite3.connect(str(path))
    try:
        res = conn.execute("PRAGMA integrity_check").fetchone()
    except sqlite3.DatabaseError:
        return False
    finally:
        conn.close()
    return bool(res) and str(res[0]).lower() == "ok"


def backup_database(db_path: str, *, directory=None) -> Path:
    """Write a verified snapshot of ``db_path`` using SQLite's online backup.

    Returns the path of the new backup file. Raises if the source does not
    exist or the snapshot fails its integrity check.
    """
    source = Path(db_path)
    if not source.is_file():
        raise FileNotFoundError(f"no database to back up: {source}")
    folder = directory if directory is not None else backups_dir()
    folder.mkdir(parents=True, exist_ok=True)
    prefix = backup_prefix(db_path)
    dest = folder / f"{prefix}-{_timestamp()}.db"
    # Two backups in the same second would otherwise share a name and the
    # later write would silently replace the earlier one.
    suffix = 1
    while dest.exists():
        dest = folder / f"{prefix}-{_timestamp()}-{suffix}.db"
        suffix += 1
    src = sqlite3.connect(str(source))
    try:
        dst = sqlite3.connect(str(dest))
        try:
            src.backup(dst)
            dst.commit()
        finally:
            dst.close()
    finally:
        src.close()
    if not _integrity_ok(dest):
        try:
            dest.unlink()
        except OSError:
            pass
        raise RuntimeError("backup failed integrity check")
    # Only after the snapshot is verified: a failed backup leaves the existing
    # history untouched.
    prune_backups(db_path, directory=folder)
    return dest


def restore_database(backup_path: str | Path, db_path: str) -> Path:
    """Verify ``backup_path``, keep current db as ``<name>.pre-restore``, swap.

    Removes any WAL/SHM/journal sidecars from the live database before the swap,
    copies them to the safety backup if present, verifies the restored file,
    and restores the original file mode.
    """
    bpath = Path(backup_path)
    if not _integrity_ok(bpath):
        raise ValueError(f"backup failed integrity check: {bpath}")
    db = Path(db_path)
    safety = db.with_suffix(db.suffix + ".pre-restore")
    sidecar_suffixes = ("-wal", "-shm", "-journal")

    # Preserve the destination file mode if the file exists.
    mode = None
    if db.exists():
        mode = stat.S_IMODE(db.stat().st_mode)

    # Copy the live database and its sidecars to the safety backup BEFORE removing sidecars.
    if db.exists():
        shutil.copy2(db, safety)
        for suffix in sidecar_suffixes:
            sidecar = Path(str(db) + suffix)
            safety_sidecar = Path(str(safety) + suffix)
            if sidecar.exists():
                shutil.copy2(sidecar, safety_sidecar)

    # Remove stale sidecars from the live database before the swap.
    for suffix in sidecar_suffixes:
        sidecar = Path(str(db) + suffix)
        sidecar.unlink(missing_ok=True)

    # Copy the verified backup over the live database.
    shutil.copy2(bpath, db)

    # Restore the original file mode.
    if mode is not None:
        os.chmod(db, mode)

    # Verify the restored database.
    if not _integrity_ok(db):
        # Restore the original file and sidecars on verification failure.
        if safety.exists():
            shutil.copy2(safety, db)
            for suffix in sidecar_suffixes:
                safety_sidecar = Path(str(safety) + suffix)
                sidecar = Path(str(db) + suffix)
                if safety_sidecar.exists():
                    shutil.copy2(safety_sidecar, sidecar)
            if mode is not None:
                os.chmod(db, mode)
        raise RuntimeError("restored copy failed its integrity check")

    return safety
