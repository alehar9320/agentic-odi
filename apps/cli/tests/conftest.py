"""Shared conftest for CLI tests.

Enables the experimental_connectors flag so connector management commands
work in tests (the flag gates add/health/ingest per issue #84).
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _enable_experimental_connectors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENTIC_ODI_FLAG_EXPERIMENTAL_CONNECTORS", "1")
