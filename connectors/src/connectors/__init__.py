"""External connectors for Agentic ODI."""

from connectors.factory import build_connector, known_kinds, register_kind
from connectors.models import (
    ConnectorConfig,
    HealthStatus,
    IngestBatch,
    IngestRecord,
    McpConnectorSettings,
)
from connectors.protocol import Connector
from connectors.registry import (
    ConnectorNotFoundError,
    ConnectorRegistry,
    DuplicateConnectorError,
    UnknownConnectorKindError,
)
from connectors.sink import IngestSink, get_default_sink

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
    "UnknownConnectorKindError",
    "build_connector",
    "get_default_sink",
    "known_kinds",
    "register_kind",
]
