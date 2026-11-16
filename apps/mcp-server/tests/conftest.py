"""Shared fixtures for the MCP server tests.

Importing ``agentic_odi_mcp_server`` builds no store, so a test names its own
here rather than setting an environment variable before import. Each test gets
a fresh in-memory repository; nothing is shared between tests.
"""

from __future__ import annotations

from collections.abc import Generator

import pytest
from agentic_odi_core import InMemoryRepository
from agentic_odi_mcp_server import mcp_server


@pytest.fixture(autouse=True)
def configured_server() -> Generator[None, None, None]:
    mcp_server.configure(InMemoryRepository())
    yield
    mcp_server._repo = None
    mcp_server._service = None
