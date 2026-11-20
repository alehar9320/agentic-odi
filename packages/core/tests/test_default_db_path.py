"""Tests for the canonical ODI database path resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from agentic_odi_core.paths import default_odi_db_path


def test_env_override_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENTIC_ODI_DB", "/tmp/custom.db")
    assert default_odi_db_path() == Path("/tmp/custom.db")


def test_default_is_absolute(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AGENTIC_ODI_DB", raising=False)
    assert default_odi_db_path().is_absolute()


def test_default_shape_under_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("AGENTIC_ODI_DB", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    assert default_odi_db_path() == tmp_path / ".agentic-odi" / "odi.db"