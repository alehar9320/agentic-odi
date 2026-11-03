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
from datetime import datetime
from pathlib import Path

from agentic_odi_core.errors import StoreCorrupt

#: Where backups live. Beside the database, so a person who moves the database
#: moves its history with it and a restore does not depend on a platform path.
DEFAULT_BACKUP_DIR = "~/.agentic-odi/backups"

BACKUP_DIR_ENV = "AGENTIC_ODI_BACKUP_DIR"

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


def latest_backup(db_path: str, *, directory: Path | None = None) -> Path | None:
    """Return the newest existing backup for a database, or ``None``.

    Newest is by filename, which is a UTC timestamp, so it does not depend on
    filesystem mtime resolution.
    """
    folder = directory if directory is not None else backups_dir()
    if not folder.is_dir():
        return None
    prefix = backup_prefix(db_path)
    candidates = sorted(
        (path for path in folder.glob(f"{prefix}-*.db") if path.is_file()),
        key=lambda path: path.name,
        reverse=True,
    )
    return candidates[0] if candidates else None


def format_backup_time(backup: Path) -> str:
    """Read the UTC time out of a backup filename, as ``HH:MM`` when possible."""
    stem = backup.stem
    _, _, stamp = stem.partition("-")
    try:
        parsed = datetime.strptime(stamp, "%Y%m%dT%H%M%SZ")
    except ValueError:
        return backup.name
    return parsed.strftime("%H:%M")


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
        backup_line = f"Last backup: {format_backup_time(resolved)} ({resolved.name})."
    return (
        f"{error.label} failed its integrity check: {error.path}. "
        f"{backup_line} The file has been left untouched — restore a backup before opening it again."
    )
