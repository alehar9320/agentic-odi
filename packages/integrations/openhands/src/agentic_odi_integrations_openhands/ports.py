"""Ports (protocols) the orchestrator engine depends on.

Adapters live in ``adapters/`` and implement these ports against external
systems (ODI core, OpenHands Cloud, issue trackers, the system clock). The
engine imports only ports, never concrete implementations, so the
orchestrator can be tested in isolation from ODI core and any external
service.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from agentic_odi_core import ScheduledWork, SignalKind


class SignalPort(Protocol):
    """Record a signal in the ODI inbox."""

    def record_signal(
        self,
        kind: SignalKind,
        title: str,
        subject_kind: str | None = None,
        subject_id: str | None = None,
        severity: str = "info",
        detail: str | None = None,
        discriminator: str = "",
    ) -> object: ...


class SchedulePort(Protocol):
    """Read and update scheduled work in the ODI store."""

    def list_scheduled_work(
        self, status: str | None = None
    ) -> list[ScheduledWork]: ...

    def get_scheduled_work(self, work_id: str) -> ScheduledWork | None: ...

    def update_scheduled_work(
        self, work_id: str, updates: dict
    ) -> ScheduledWork | None: ...


class ClockPort(Protocol):
    """Provide the current time (injectable for tests)."""

    def now(self) -> datetime: ...


class IssueTrackerPort(Protocol):
    """Read issues from an issue tracker (Commit 3 adds implementations)."""

    def due_issues(self, since: datetime | None = None) -> list[dict]: ...
