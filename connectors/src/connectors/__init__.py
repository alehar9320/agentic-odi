"""Pluggable external-integration connectors for Agentic ODI (MCP client)."""

from __future__ import annotations

from .errors import (
    ConnectorNotFoundError,
    DuplicateConnectorError,
    RegistryError,
    UnknownConnectorKindError,
)
from .models import (
    ConnectorConfig,
    HealthStatus,
    IngestBatch,
    IngestRecord,
    McpConnectorSettings,
)
from .protocol import Connector
from .sink import IngestSink

__all__ = [
    "Connector",
    "ConnectorConfig",
    "ConnectorNotFoundError",
    "DuplicateConnectorError",
    "HealthStatus",
    "IngestBatch",
    "IngestRecord",
    "IngestSink",
    "McpConnectorSettings",
    "RegistryError",
    "UnknownConnectorKindError",
]
