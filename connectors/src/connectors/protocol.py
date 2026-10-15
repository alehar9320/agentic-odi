"""The structural interface every connector implements."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .models import HealthStatus, IngestBatch


@runtime_checkable
class Connector(Protocol):
    kind: str
    name: str

    async def health(self) -> HealthStatus: ...

    async def ingest(self) -> IngestBatch: ...
