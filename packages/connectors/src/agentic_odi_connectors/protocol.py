"""Connector protocol implemented by every external integration kind."""

from __future__ import annotations

from abc import ABC, abstractmethod

from agentic_odi_connectors.models import HealthStatus, IngestBatch, LinkPreviewData


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

    async def preview(self, external_id: str) -> LinkPreviewData | None:
        """Describe one external item by id, or return ``None``.

        ``None`` means this connector cannot describe the item (unsupported or
        unavailable). The default is concrete, not abstract, so a connector
        without preview support inherits this answer and cannot break.
        """
        return None
