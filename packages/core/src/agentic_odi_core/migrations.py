"""A numbered migration ledger for the local SQLite stores.

Both local stores used to migrate by comparing ``PRAGMA table_info`` against a
dict of expected columns on every open and running ``ALTER TABLE`` for each one
that was missing. That works for exactly one kind of change — an additive
column — and it leaves no record of what has already run: there is no
``PRAGMA user_version``, so nothing can tell a v3 database from a v7 one, and a
backfill, an index change, or a table rebuild has nowhere to live. Two processes
that open the same file race the same ``ALTER TABLE`` and are saved only by the
busy timeout.

This module is the replacement, mirroring the browser store's registry
(``apps/studio/src/bff/store/migrations.ts``): an ordered tuple of steps keyed by
the version each produces, a helper that names the missing version instead of
failing mid-upgrade, and a runner that applies every step newer than the stored
version inside one ``BEGIN IMMEDIATE`` transaction and writes the new
``user_version`` in that same transaction.

The rule the ledger exists to enforce: a schema change is a new numbered
migration, never an edit to an old one. ``tests/scripts/test_migrations_registry.py``
fails when the current version is raised without a registered step.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from agentic_odi_core.errors import MigrationError
from agentic_odi_core.events import new_event_id

#: Columns the old ``_migrate_events_table`` added on every open of ``odi.db``.
#: They are migration 1 now, applied once and recorded in ``PRAGMA user_version``.
EVENT_COLUMNS: dict[str, str] = {
    "event_id": "TEXT",
    "workspace_id": "TEXT NOT NULL DEFAULT 'local'",
    "device_id": "TEXT NOT NULL DEFAULT 'local'",
    "server_seq": "INTEGER",
}


@dataclass(frozen=True)
class Migration:
    """One step in the ladder. It creates or alters schema; it never clears it."""

    version: int
    description: str
    apply: Callable[[sqlite3.Connection], None]


def _migration_1(connection: sqlite3.Connection) -> None:
    """Ensure the event columns, then backfill an ``event_id`` for every old row.

    This is the idempotent ``PRAGMA table_info`` logic the store used to run on
    every open, now numbered and recorded. It reads the columns that exist
    rather than assuming the pre-change shape, so a database that already has
    them (a fresh one, or one already upgraded) is unchanged.
    """
    existing = {row[1] for row in connection.execute("PRAGMA table_info(events)").fetchall()}
    for column, definition in EVENT_COLUMNS.items():
        if column not in existing:
            connection.execute(f"ALTER TABLE events ADD COLUMN {column} {definition}")

    missing_ids = [
        row[0]
        for row in connection.execute(
            "SELECT id FROM events WHERE event_id IS NULL OR event_id = ''"
        ).fetchall()
    ]
    for row_id in missing_ids:
        connection.execute(
            "UPDATE events SET event_id = ? WHERE id = ?",
            (new_event_id(), row_id),
        )


#: Every step for ``odi.db`` keyed by the version it produces. Versions are
#: contiguous from 1; ``test_migrations_registry.py`` fails if one is missing.
MIGRATIONS: tuple[Migration, ...] = (
    Migration(
        1,
        "Add the event identity columns and backfill event_id.",
        _migration_1,
    ),
)

#: The version this build opens. Raising it without a registered step fails the
#: registry test by name, instead of failing an upgrade in a user's database.
CURRENT_VERSION: int = len(MIGRATIONS)


def current_version(connection: sqlite3.Connection) -> int:
    """The schema version recorded in the file, ``0`` for a pre-ledger database."""
    return int(connection.execute("PRAGMA user_version").fetchone()[0])


def migration_steps(
    migrations: Sequence[Migration], from_version: int, to_version: int
) -> tuple[Migration, ...]:
    """The steps a database at ``from_version`` runs to reach ``to_version``.

    Names the missing version rather than skipping it: a gap in the registry is
    a build error, not a database that quietly stays old.
    """
    registered = {step.version: step for step in migrations}
    steps: list[Migration] = []
    for version in range(from_version + 1, to_version + 1):
        step = registered.get(version)
        if step is None:
            raise MigrationError(
                f"No migration registered for version {version}; add it before "
                f"raising the schema version to {to_version}."
            )
        steps.append(step)
    return tuple(steps)


def migrate(
    connection: sqlite3.Connection,
    migrations: Sequence[Migration],
    *,
    label: str = "database",
) -> int:
    """Apply every step newer than the stored version and return the new version.

    The whole ladder runs in one transaction and the ``user_version`` write
    happens in that same transaction, so a crash leaves the file at its previous
    version rather than half-migrated. A database already at the target version
    is a no-op.

    ``migrations`` is passed explicitly because two stores share this runner:
    ``odi.db`` uses :data:`MIGRATIONS` and ``studio.db`` uses its own registry.
    """
    start = current_version(connection)
    target = max((step.version for step in migrations), default=0)
    if start >= target:
        return start

    steps = migration_steps(migrations, start, target)

    # Both callers run the ladder while their own open is still in progress, so
    # the runner must tolerate an enclosing transaction. A savepoint nests
    # cleanly; a bare BEGIN IMMEDIATE would raise "cannot start a transaction
    # within a transaction". When the connection is idle the savepoint is
    # released into a real BEGIN IMMEDIATE, so the ladder is atomic on its own.
    nested = connection.in_transaction
    if nested:
        connection.execute("SAVEPOINT odi_migrate")
    else:
        connection.execute("BEGIN IMMEDIATE")
    try:
        for step in steps:
            try:
                step.apply(connection)
            except sqlite3.Error as exc:
                raise MigrationError(
                    f"{label}: migration {step.version} ({step.description}) failed: {exc}"
                ) from exc
        connection.execute(f"PRAGMA user_version = {int(target)}")
    except BaseException:
        connection.execute("ROLLBACK TO odi_migrate" if nested else "ROLLBACK")
        if nested:
            connection.execute("RELEASE odi_migrate")
        raise
    if nested:
        connection.execute("RELEASE odi_migrate")
    else:
        connection.commit()
    return target
