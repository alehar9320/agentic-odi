"""ODI core adapter implementing SignalPort and SchedulePort.

This adapter bridges the orchestrator engine's ports to ``agentic_odi_core``.
The engine never imports ``agentic_odi_core`` directly; it only knows the
port protocols defined in :mod:`ports`.
"""

from __future__ import annotations

from agentic_odi_core import ODIService, build_repository

from agentic_odi_integrations_openhands.ports import SchedulePort, SignalPort


class OdiSignalAdapter(SignalPort):
    """Write signals to the ODI store via ODIService."""

    def __init__(self, service: ODIService | None = None) -> None:
        self._service = service or ODIService(build_repository())

    def record_signal(
        self,
        kind,
        title: str,
        subject_kind: str | None = None,
        subject_id: str | None = None,
        severity: str = "info",
        detail: str | None = None,
        discriminator: str = "",
    ) -> object:
        return self._service.record_signal(
            kind=kind,
            title=title,
            subject_kind=subject_kind,
            subject_id=subject_id,
            severity=severity,
            detail=detail,
            discriminator=discriminator,
        )


class OdiScheduleAdapter(SchedulePort):
    """Read and update scheduled work via ODIService."""

    def __init__(self, service: ODIService | None = None) -> None:
        self._service = service or ODIService(build_repository())

    def list_scheduled_work(self, status: str | None = None):
        return self._service.list_scheduled_work(status=status)

    def get_scheduled_work(self, work_id: str):
        return self._service.repo.get_scheduled_work(work_id)

    def update_scheduled_work(self, work_id: str, updates: dict):
        return self._service.repo.update_scheduled_work(work_id, updates)
