"""Isolate each test's Studio memory database from the developer's home."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def isolate_studio_memory(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AGENTIC_ODI_STUDIO_DB", str(tmp_path / "studio.db"))
