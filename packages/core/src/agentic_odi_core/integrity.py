"""A bounded SQLite integrity gate for the local stores.

The repository and the Studio memory are each a single SQLite file. A damaged
file must fail the boot with a message a person can act on, not a traceback,
and the check must be cheap enough that a healthy boot is unchanged.

The bound is a **budget of SQLite VM opcodes**, spent through a progress
handler: ``quick_check`` is aborted once the budget is exhausted and the store
is reported as ``deferred`` rather than scanned to completion. ``quick_check``
on the reference 50,000-row store spends roughly 0.3M opcodes and about 7ms, so
the default budget is over 150x that — a healthy store is always fully checked,
while a pathological multi-gigabyte file cannot stall boot. A deferred check is
recorded by the caller; a scheduled full check is a later slice.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

from agentic_odi_core.errors import StoreCorrupt

#: VM opcodes the boot check may spend before it gives up and defers.
BOOT_CHECK_VM_BUDGET = 50_000_000

#: Problems kept from the full check that follows a failed quick check.
MAX_PROBLEMS = 20


@dataclass(frozen=True)
class IntegrityResult:
    """The outcome of a boot check.

    ``status`` is one of ``ok``, ``corrupt``, or ``deferred``. ``deferred``
    means the budget ran out before the check finished; the store is left
    unchecked and the caller records that rather than treating it as damage.
    """

    status: str
    problems: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.status == "ok"


def check_integrity(
    connection: sqlite3.Connection, *, budget: int = BOOT_CHECK_VM_BUDGET
) -> IntegrityResult:
    """Run a bounded ``quick_check`` and classify the result.

    A file that is not a database at all (a text file, a truncated header)
    raises ``sqlite3.DatabaseError`` from the pragma; that is damage, not an
    error to propagate, so it comes back as ``corrupt``.
    """
    spent = {"ops": 0}

    def _trip() -> int:
        spent["ops"] += 1
        return 1

    connection.set_progress_handler(_trip, budget)
    try:
        rows = connection.execute("PRAGMA quick_check").fetchall()
    except sqlite3.OperationalError as exc:
        # The progress handler aborts the statement with "interrupted" once the
        # budget is spent; anything else is damage.
        if "interrupt" in str(exc).lower():
            return IntegrityResult(status="deferred")
        return IntegrityResult(status="corrupt", problems=[str(exc)])
    except sqlite3.DatabaseError as exc:
        return IntegrityResult(status="corrupt", problems=[str(exc)])
    finally:
        connection.set_progress_handler(None, 0)

    problems = [str(row[0]) for row in rows if row and str(row[0]).lower() != "ok"]
    if not problems:
        return IntegrityResult(status="ok")
    return IntegrityResult(status="corrupt", problems=problems[:MAX_PROBLEMS])


def deep_check(connection: sqlite3.Connection) -> list[str]:
    """Collect up to :data:`MAX_PROBLEMS` rows from a full ``integrity_check``.

    Only run after a failed quick check, so the cost is paid on the failure
    path where boot is stopping anyway.
    """
    try:
        rows = connection.execute("PRAGMA integrity_check").fetchall()
    except sqlite3.DatabaseError as exc:
        return [str(exc)]
    return [str(row[0]) for row in rows if row and str(row[0]).lower() != "ok"][:MAX_PROBLEMS]


def ensure_intact(
    connection: sqlite3.Connection,
    path: str,
    *,
    label: str = "Database",
    budget: int = BOOT_CHECK_VM_BUDGET,
) -> IntegrityResult:
    """Gate a store on open.

    Returns the check result when the file is intact or the check was deferred.
    Raises :class:`StoreCorrupt` when the file is damaged, carrying the path and
    the problems found. The file itself is never touched.
    """
    result = check_integrity(connection, budget=budget)
    if result.status == "corrupt":
        problems = deep_check(connection) or result.problems
        raise StoreCorrupt(path, problems, label=label)
    return result
