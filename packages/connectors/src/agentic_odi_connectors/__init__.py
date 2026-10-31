"""External connectors for Agentic ODI."""

import json
import sys

from agentic_odi_connectors.catalog import (
    AREA_LABELS,
    PRESETS,
    ConnectorPreset,
    UnknownAreaError,
    UnknownPresetError,
    connector_config_from_preset,
    get_preset,
    list_presets,
)
from agentic_odi_connectors.factory import build_connector, known_kinds, register_kind
from agentic_odi_connectors.http import ConnectorHTTPClient, get_http_client
from agentic_odi_connectors.mapping import (
    EvidenceDraft,
    drafts_from_batch,
    validate_evidence_draft,
)
from agentic_odi_connectors.marketplace import (
    MarketplaceCache,
    MarketplaceListing,
    MarketplaceService,
    connector_config_from_listing,
    env_vars_in_listing,
    listing_from_preset,
    listing_from_registry_record,
)
from agentic_odi_connectors.models import (
    ConfigurationError,
    ConnectorConfig,
    HealthStatus,
    IngestBatch,
    IngestRecord,
    McpConnectorSettings,
    RestConnectorSettings,
)
from agentic_odi_connectors.paths import config_path
from agentic_odi_connectors.protocol import Connector
from agentic_odi_connectors.registry import (
    ConnectorNotFoundError,
    ConnectorRegistry,
    DuplicateConnectorError,
    UnknownConnectorKindError,
)
from agentic_odi_connectors.sink import IngestSink, get_default_sink

KNOWN_KINDS = {"in_memory", "rest", "mcp"}

REQUIRED_KEYS = ("kind", "health_url", "ingest_endpoint")


def validate_connector_config(config: dict) -> dict:
    """Validate a connector preset config dict.

    Checks that required keys are present, kind is a registered kind,
    health_url is an HTTP(S) URL, and ingest_endpoint is non-empty.
    Returns the config unchanged on success; raises ConfigurationError
    with the list of bad keys on failure.
    """
    bad: list[str] = []
    for key in REQUIRED_KEYS:
        if key not in config or config[key] in (None, ""):
            bad.append(key)
    if "kind" in config and config["kind"] not in KNOWN_KINDS:
        bad.append("kind")
    if (
        "health_url" in config
        and config["health_url"] not in (None, "")
        and not config["health_url"].startswith(("http://", "https://"))
    ):
        bad.append("health_url")
    if bad:
        raise ConfigurationError(bad)
    return config


def _load_and_validate_presets() -> None:
    """Read connectors.json and validate every preset at import time.

    Exits the process with code 1 if any preset is invalid.
    """
    path = config_path()
    if not path.exists():
        return
    try:
        with path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, ValueError) as exc:
        print(f"Error reading connectors config: {exc}", file=sys.stderr)
        sys.exit(1)
    presets = payload.get("connectors", [])
    if not isinstance(presets, list):
        print("Error: connectors config must contain a 'connectors' list", file=sys.stderr)
        sys.exit(1)
    bad_presets = []
    for preset in presets:
        try:
            validate_connector_config(preset)
        except ConfigurationError as exc:
            bad_presets.append((preset, exc.keys))
    if bad_presets:
        for preset, keys in bad_presets:
            print(
                f"Error: invalid connector preset {preset.get('name', 'unnamed')}: {', '.join(keys)}",
                file=sys.stderr,
            )
        sys.exit(1)


_load_and_validate_presets()

__all__ = [
    "AREA_LABELS",
    "ConfigurationError",
    "PRESETS",
    "KNOWN_KINDS",
    "REQUIRED_KEYS",
    "validate_connector_config",
    "Connector",
    "ConnectorConfig",
    "ConnectorHTTPClient",
    "ConnectorNotFoundError",
    "ConnectorPreset",
    "ConnectorRegistry",
    "DuplicateConnectorError",
    "EvidenceDraft",
    "HealthStatus",
    "IngestBatch",
    "IngestRecord",
    "IngestSink",
    "MarketplaceCache",
    "MarketplaceListing",
    "MarketplaceService",
    "McpConnectorSettings",
    "UnknownAreaError",
    "RestConnectorSettings",
    "UnknownConnectorKindError",
    "UnknownPresetError",
    "build_connector",
    "config_path",
    "connector_config_from_listing",
    "connector_config_from_preset",
    "drafts_from_batch",
    "env_vars_in_listing",
    "get_default_sink",
    "get_http_client",
    "get_preset",
    "known_kinds",
    "list_presets",
    "listing_from_preset",
    "listing_from_registry_record",
    "register_kind",
    "validate_evidence_draft",
]
