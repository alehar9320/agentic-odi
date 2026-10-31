"""Repository health reflects whether the store can be queried."""

from __future__ import annotations

from agentic_odi_core.factory import build_repository


def test_in_memory_repository_is_healthy():
    repo = build_repository(":memory:")

    assert repo.health() is True


def test_sqlite_repository_is_healthy(tmp_path):
    repo = build_repository(str(tmp_path / "health.db"))

    assert repo.health() is True

    repo.close()

    assert repo.health() is False
