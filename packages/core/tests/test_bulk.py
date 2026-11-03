"""ALH-196 (M2-03.1) — the bulk record an undo token rides.

A bulk operation is addressed later, possibly from another process, so the inverse must be
readable from the store rather than held in memory: the same persistence route the scheduled
work record already takes.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from agentic_odi_core.models import BulkChange, BulkOperation
from agentic_odi_core.repository import InMemoryRepository
from agentic_odi_core.sqlite_repository import SQLiteRepository

APPLIED = datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc)
UNDONE = datetime(2026, 11, 3, 12, 30, tzinfo=timezone.utc)


def _change(outcome_id: str) -> BulkChange:
    return BulkChange(
        outcome_id=outcome_id,
        before={"step_id": None, "theme_ids": [], "tags": []},
        after={"step_id": "s-2", "theme_ids": ["t-1"], "tags": ["churn"]},
    )


def _operation(token: str, applied_at: datetime = APPLIED) -> BulkOperation:
    return BulkOperation(
        id=token,
        applied_at=applied_at,
        requested=2,
        changes=[_change("o-1")],
        skipped=[{"id": "o-9", "reason": "outcome not found"}],
    )


@pytest.fixture(params=["memory", "sqlite"])
def repo(request: pytest.FixtureRequest, tmp_path: Path):
    if request.param == "memory":
        return InMemoryRepository()
    return SQLiteRepository(db_path=str(tmp_path / "odi.db"))


def test_a_bulk_operation_is_readable_by_its_token(repo) -> None:
    repo.add_bulk_operation(_operation("b-1"))
    read = repo.get_bulk_operation("b-1")
    assert read is not None
    assert read.changes[0].after["step_id"] == "s-2"
    assert read.undone_at is None


def test_an_unknown_token_reads_as_nothing(repo) -> None:
    assert repo.get_bulk_operation("b-nope") is None


def test_bulk_operations_are_listed_in_creation_order(repo) -> None:
    repo.add_bulk_operation(_operation("b-2", APPLIED))
    repo.add_bulk_operation(_operation("b-1", APPLIED))
    repo.add_bulk_operation(_operation("b-3", APPLIED))
    assert [op.id for op in repo.list_bulk_operations()] == ["b-2", "b-1", "b-3"]


def test_marking_a_bulk_operation_undone_persists(repo) -> None:
    repo.add_bulk_operation(_operation("b-1"))
    updated = repo.update_bulk_operation("b-1", {"undone_at": UNDONE})
    assert updated is not None and updated.undone_at == UNDONE
    assert repo.get_bulk_operation("b-1").undone_at == UNDONE


def test_a_bulk_operation_survives_a_reopen(tmp_path: Path) -> None:
    path = str(tmp_path / "odi.db")
    store = SQLiteRepository(db_path=path)
    store.add_bulk_operation(_operation("b-1"))
    reopened = SQLiteRepository(db_path=path)
    read = reopened.get_bulk_operation("b-1")
    assert read is not None
    assert read.changes[0].before["theme_ids"] == []
    assert read.skipped[0]["reason"] == "outcome not found"
