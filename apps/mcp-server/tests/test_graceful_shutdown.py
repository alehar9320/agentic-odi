"""Tests for the MCP server's graceful shutdown path."""

from __future__ import annotations

import signal
from collections.abc import Generator
from typing import Any

import pytest
from agentic_odi_mcp_server import mcp_server


@pytest.fixture(autouse=True)
def reset_shutdown_state() -> Generator[None, Any, None]:
    """Allow each test to drive the shutdown path from a clean slate."""
    mcp_server._shutdown_complete = False
    yield
    mcp_server._shutdown_complete = False


class _RecordingRepo:
    def __init__(self) -> None:
        self.commits = 0
        self.closes = 0

    def commit(self) -> None:
        self.commits += 1

    def close(self) -> None:
        self.closes += 1


@pytest.fixture
def recorder(monkeypatch: pytest.MonkeyPatch) -> _RecordingRepo:
    repo = _RecordingRepo()
    monkeypatch.setattr(mcp_server, "_repo", repo)
    return repo


def test_shutdown_store_commits_and_closes(recorder: _RecordingRepo) -> None:
    mcp_server.shutdown_store()

    assert recorder.commits == 1
    assert recorder.closes == 1


def test_shutdown_store_is_idempotent(recorder: _RecordingRepo) -> None:
    mcp_server.shutdown_store()
    mcp_server.shutdown_store()
    mcp_server.shutdown_store()

    assert recorder.commits == 1
    assert recorder.closes == 1


def test_shutdown_store_closes_even_when_commit_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FailingRepo(_RecordingRepo):
        def commit(self) -> None:
            raise RuntimeError("commit failed")

    repo = _FailingRepo()
    monkeypatch.setattr(mcp_server, "_repo", repo)

    with pytest.raises(RuntimeError, match="commit failed"):
        mcp_server.shutdown_store()

    assert repo.closes == 1


def test_setup_graceful_shutdown_installs_handlers() -> None:
    original_int = signal.getsignal(signal.SIGINT)
    original_term = signal.getsignal(signal.SIGTERM)
    try:
        mcp_server.setup_graceful_shutdown()

        assert signal.getsignal(signal.SIGINT) is not original_int
        assert signal.getsignal(signal.SIGTERM) is not original_term
    finally:
        signal.signal(signal.SIGINT, original_int)
        signal.signal(signal.SIGTERM, original_term)


def test_signal_handler_flushes_the_store(
    recorder: _RecordingRepo,
) -> None:
    original_int = signal.getsignal(signal.SIGINT)
    original_term = signal.getsignal(signal.SIGTERM)
    try:
        mcp_server.setup_graceful_shutdown()
        handler = signal.getsignal(signal.SIGTERM)
        assert callable(handler)

        handler(signal.SIGTERM, None)
    finally:
        signal.signal(signal.SIGINT, original_int)
        signal.signal(signal.SIGTERM, original_term)

    assert recorder.commits == 1
    assert recorder.closes == 1


def test_signal_handler_chains_to_the_previous_handler(
    recorder: _RecordingRepo,
) -> None:
    original_int = signal.getsignal(signal.SIGINT)
    original_term = signal.getsignal(signal.SIGTERM)
    seen: list[int] = []
    try:
        signal.signal(signal.SIGTERM, lambda signum, frame: seen.append(signum))
        mcp_server.setup_graceful_shutdown()
        handler = signal.getsignal(signal.SIGTERM)
        assert callable(handler)

        handler(signal.SIGTERM, None)
    finally:
        signal.signal(signal.SIGINT, original_int)
        signal.signal(signal.SIGTERM, original_term)

    assert seen == [signal.SIGTERM]
    assert recorder.commits == 1


@pytest.mark.asyncio
async def test_lifespan_closes_the_store_on_exit(recorder: _RecordingRepo) -> None:
    async with mcp_server._lifespan(mcp_server.mcp):
        assert recorder.closes == 0

    assert recorder.commits == 1
    assert recorder.closes == 1


def test_in_memory_repository_commit_and_close_are_no_ops() -> None:
    from agentic_odi_core.repository import InMemoryRepository

    repo = InMemoryRepository()
    repo.commit()
    repo.close()
    repo.close()
