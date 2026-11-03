from __future__ import annotations

import os

# Pinned before anything reaches the factory: a test that ever lets
# `create_server()` build its own store gets an in-memory one, not a home folder.
os.environ["AGENTIC_ODI_DB"] = ":memory:"

import pytest  # noqa: E402
from agentic_odi_core.repository import InMemoryRepository  # noqa: E402
from agentic_odi_mcp_server import create_server  # noqa: E402
from fastmcp import FastMCP  # noqa: E402


@pytest.fixture
def repository() -> InMemoryRepository:
    """A store this test owns outright — isolation by construction, not by clearing."""
    return InMemoryRepository()


@pytest.fixture
def mcp(repository: InMemoryRepository) -> FastMCP:
    """A server built by the factory around that store."""
    return create_server(repository=repository)
