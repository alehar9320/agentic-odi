"""Pluggable external-integration connectors for Agentic ODI (MCP client)."""

from __future__ import annotations

from .errors import (
    ConnectorNotFoundError,
    DuplicateConnectorError,
    RegistryError,
    UnknownConnectorKindError,
)
from .mcp import MCPClientConnector
from .models import (
    ConnectorConfig,
    HealthStatus,
    IngestBatch,
    IngestRecord,
    McpConnectorSettings,
)
from .protocol import Connector
from .registry import ConnectorRegistry, build_connector
from .sink import IngestSink

__all__ = [
    "Connector",
    "ConnectorConfig",
    "ConnectorNotFoundError",
    "ConnectorRegistry",
    "DuplicateConnectorError",
    "HealthStatus",
    "IngestBatch",
    "IngestRecord",
    "IngestSink",
    "McpConnectorSettings",
    "RegistryError",
    "UnknownConnectorKindError",
    "build_connector",
    "MCPClientConnector",
]
