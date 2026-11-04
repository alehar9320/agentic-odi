"""Event-store contract shared by local SQLite and cloud adapters."""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any, Protocol, TypedDict

DEFAULT_WORKSPACE = "local"
DEFAULT_DEVICE = "local"


class Event(TypedDict):
    """A single append-only domain event."""

    id: int
    event_id: str
    workspace_id: str
    device_id: str
    timestamp: str
    type: str
    payload: dict[str, Any]
    server_seq: int | None


class EventStore(Protocol):
    """Persistence boundary for the append-only event log."""

    def append(
        self,
        event_type: str,
        payload: dict[str, Any],
        *,
        event_id: str | None = None,
        workspace_id: str = DEFAULT_WORKSPACE,
        device_id: str = DEFAULT_DEVICE,
    ) -> Event: ...

    def get_stream(
        self,
        *,
        workspace_id: str | None = None,
        after_server_seq: int = 0,
        after_id: int = 0,
        unsynced_only: bool = False,
        replay_order: bool = False,
    ) -> list[Event]: ...

    def insert_remote(self, events: list[Event]) -> int: ...

    def mark_synced(self, server_seqs: dict[str, int]) -> int: ...

    def retag_workspace(self, old: str, new: str) -> int: ...

    def max_server_seq(self, workspace_id: str) -> int: ...

    def get_cursor(self, workspace_id: str) -> int: ...

    def set_cursor(self, workspace_id: str, remote_url: str, seq: int) -> None: ...

    def pending_count(self, workspace_id: str) -> int: ...

    def clear(self, *, workspace_id: str | None = None) -> None: ...

    def close(self) -> None: ...


def new_event_id() -> str:
    """Return a globally unique, client-generated event identifier."""
    return uuid.uuid4().hex


def default_device_path() -> Path:
    return Path(os.path.expanduser("~/.agentic-odi/device_id"))


def resolve_device_id(path: Path | None = None) -> str:
    """Return a stable random device id, creating it on first use.

    The id is deliberately random: it must not reveal a hostname, user, or
    anything else about the device.
    """
    configured = os.environ.get("AGENTIC_ODI_DEVICE_ID")
    if configured:
        return configured

    device_path = path or default_device_path()
    try:
        existing = device_path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        existing = ""

    if existing:
        return existing

    device_path.parent.mkdir(parents=True, exist_ok=True)
    device_id = uuid.uuid4().hex
    device_path.write_text(device_id + "\n", encoding="utf-8")
    return device_id
