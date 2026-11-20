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
from datetime import datetime, timedelta, timezone
from pathlib import Path

from agentic_odi_core.errors import StoreCorrupt

#: Where backups live. Beside the database, so a person who moves the database
#: moves its history with it and a restore does not depend on a platform path.
DEFAULT_BACKUP_DIR = "~/.agentic-odi/backups"

BACKUP_DIR_ENV = "AGENTIC_ODI_BACKUP_DIR"

#: How many backups to keep at most. The newest ``keep`` always survive, and
#: one backup per calendar day is retained for the last week on top of that.
BACKUP_KEEP_ENV = "AGENTIC_ODI_BACKUP_KEEP"
DEFAULT_BACKUP_KEEP = 14

#: The number of recent calendar days that always keep one backup each,
#: regardless of the ``keep`` count.
_BACKUP_DAILY_RETENTION_DAYS = 7


def _env_int(name: str, default: int, *, minimum: int) -> int:
    """Parse an integer environment variable, raising on an invalid value.

    An absent or empty variable means "use the default". A present but
    non-integer or out-of-range value raises with the variable name in the
    message so the operator sees which setting they chose.
    """
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer >= {minimum}, got {raw!r}") from exc
    if value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}, got {value}")
    return value


def _backup_keep() -> int:
    """Resolve the retention count from the environment, refusing bad values.

    A non-positive keep would delete the backup just written, so it falls back
    to the default rather than honouring it.
    """
    try:
        return _env_int(BACKUP_KEEP_ENV, DEFAULT_BACKUP_KEEP, minimum=1)
    except ValueError:
        return DEFAULT_BACKUP_KEEP


def _backup_sort_key(path: Path) -> tuple[int, str]:
    """Sort backups newest-first by mtime, filename as a tiebreaker.

    Shares the ordering with :func:`latest_backup` so the two views of the
    directory cannot disagree.
    """
    return (path.stat().st_mtime_ns, path.name)


def _calendar_day(path: Path) -> str:
    """Return the UTC calendar day a backup was written, as ``YYYY-MM-DD``.

    The filename carries a fixed-width UTC stamp, so the day is read from the
    name rather than the file's mtime. A collision suffix (``-N``) is stripped
    before parsing, matching :func:`format_backup_time`.
    """
    stem = path.stem
    _, _, stamp = stem.partition("-")
    head, sep, tail = stamp.rpartition("-")
    if sep and tail.isdigit():
        stamp = head
    try:
        parsed = datetime.strptime(stamp, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return ""
    return parsed.date().isoformat()


def prune_backups(
    db_path: str,
    *,
    keep: int | None = None,
    directory: Path | None = None,
) -> list[Path]:
    """Delete old backups, keeping the newest ``keep`` plus one per recent day.

    The newest ``keep`` backups always survive. In addition, the newest backup
    from each of the last ``_BACKUP_DAILY_RETENTION_DAYS`` calendar days is
    kept, so a day with many backups still contributes one. Oldest files are
    removed first. A failed unlink is skipped rather than raised.

    ``keep`` defaults to the configured retention count. A non-positive value
    is refused and falls back to the default rather than deleting everything.
    """
    if keep is None or keep <= 0:
        keep = _backup_keep()
    folder = directory if directory is not None else backups_dir()
    if not folder.is_dir():
        return []
    prefix = backup_prefix(db_path)
    candidates = [path for path in folder.glob(f"{prefix}-*.db") if path.is_file()]
    if not candidates:
        return []
    candidates.sort(key=_backup_sort_key, reverse=True)

    today = datetime.now(timezone.utc).date()
    recent_days = {today - timedelta(days=i) for i in range(_BACKUP_DAILY_RETENTION_DAYS)}
    recent_days_iso = {day.isoformat() for day in recent_days}

    kept: set[Path] = set()
    removed: list[Path] = []
    for path in candidates[:keep]:
        kept.add(path)
    for path in candidates[keep:]:
        day = _calendar_day(path)
        if day in recent_days_iso and path not in kept:
            kept.add(path)
            continue
        try:
            path.unlink()
        except OSError:
            continue
        removed.append(path)
    return removed


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


def latest_backup(db_path: str, *, directory: Path | None = None) -> Path | None:
    """Return the newest existing backup for a database, or ``None``.

    Newest is by modification time, with the filename as a tiebreaker. The
    filename stamp has one-second resolution, so a pair written in the same
    second differ only by their collision suffix and the clock cannot order
    them; the file's own mtime can.
    """
    folder = directory if directory is not None else backups_dir()
    if not folder.is_dir():
        return None
    prefix = backup_prefix(db_path)
    candidates = [path for path in folder.glob(f"{prefix}-*.db") if path.is_file()]
    if not candidates:
        return None
    return max(candidates, key=lambda path: (path.stat().st_mtime_ns, path.name))


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
    prune_backups(str(source), directory=folder)
    return dest


def restore_database(backup_path, db_path: str) -> Path:
    """Verify ``backup_path``, keep current db as ``<name>.pre-restore``, swap."""
    bpath = Path(backup_path)
    if not _integrity_ok(bpath):
        raise ValueError(f"backup failed integrity check: {bpath}")
    db = Path(db_path)
    safety = db.with_suffix(db.suffix + ".pre-restore")
    if db.exists():
        shutil.copy2(db, safety)
    shutil.copy2(bpath, db)
    return safety
