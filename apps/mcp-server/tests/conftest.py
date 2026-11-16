from __future__ import annotations

import os

os.environ["AGENTIC_ODI_DB"] = ":memory:"

from collections.abc import Generator
from typing import Any

import pytest
from agentic_odi_core import InMemoryRepository
from agentic_odi_mcp_server.mcp_server import configure


@pytest.fixture(autouse=True)
def reset_db() -> Generator[None, Any, None]:
    configure(InMemoryRepository())
    yield
