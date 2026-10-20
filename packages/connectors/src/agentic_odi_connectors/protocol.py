"""Connector protocol implemented by every external integration kind."""

from __future__ import annotations

from abc import ABC, abstractmethod

from agentic_odi_connectors.models import HealthStatus, IngestBatch


class Connector(ABC):
    """One named connection to an external system."""

    kind: str
    name: str

    @abstractmethod
    async def health(self) -> HealthStatus:
        """Check whether the external system is reachable."""

    @abstractmethod
    async def ingest(self) -> IngestBatch:
        """Pull data from the external system into a normalized batch."""
