"""External connectors for Agentic ODI."""

from connectors.catalog import (
    AREA_LABELS,
    PRESETS,
    ConnectorPreset,
    UnknownAreaError,
    UnknownPresetError,
    connector_config_from_preset,
    get_preset,
    list_presets,
)
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
    "AREA_LABELS",
    "PRESETS",
    "Connector",
    "ConnectorConfig",
    "ConnectorNotFoundError",
    "ConnectorPreset",
    "ConnectorRegistry",
    "DuplicateConnectorError",
    "HealthStatus",
    "IngestBatch",
    "IngestRecord",
    "IngestSink",
    "McpConnectorSettings",
    "UnknownAreaError",
    "UnknownConnectorKindError",
    "UnknownPresetError",
    "build_connector",
    "connector_config_from_preset",
    "get_default_sink",
    "get_preset",
    "known_kinds",
    "list_presets",
    "register_kind",
]
