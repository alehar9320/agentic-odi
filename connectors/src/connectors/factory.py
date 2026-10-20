"""Kind registry that maps connector configs onto Connector implementations."""

from __future__ import annotations

from collections.abc import Callable

from connectors.mcp.connector import MCPClientConnector
from connectors.models import ConnectorConfig, McpConnectorSettings, RestConnectorSettings
from connectors.protocol import Connector
from connectors.registry import UnknownConnectorKindError
from connectors.rest.connector import RestConnector, WebhookConnector

Builder = Callable[[ConnectorConfig], Connector]

_builders: dict[str, Builder] = {}


def register_kind(kind: str, builder: Builder) -> None:
    """Register a builder for a connector kind (mcp today; others later)."""
    _builders[kind] = builder


def known_kinds() -> set[str]:
    return set(_builders)


def build_connector(config: ConnectorConfig) -> Connector:
    try:
        builder = _builders[config.kind]
    except KeyError:
        raise UnknownConnectorKindError(config.kind) from None
    return builder(config)


def _build_mcp(config: ConnectorConfig) -> Connector:
    settings = McpConnectorSettings.model_validate(config.settings)
    return MCPClientConnector(name=config.name, settings=settings)


def _build_rest(config: ConnectorConfig) -> Connector:
    settings = RestConnectorSettings.model_validate(config.settings)
    return RestConnector(name=config.name, settings=settings)


def _build_webhook(config: ConnectorConfig) -> Connector:
    settings = RestConnectorSettings.model_validate(config.settings)
    return WebhookConnector(name=config.name, settings=settings, kind="webhook")


register_kind("mcp", _build_mcp)
register_kind("rest", _build_rest)
register_kind("webhook", _build_webhook)
