"""Sidecar service that manages external connector registrations.

Wraps the shared ``connectors.json`` registry and the preset catalog so the
Living Studio can register, list, delete, and health-check connectors
without depending on an MCP server round-trip. The config path is shared
with the CLI via ``agentic_odi_connectors.paths.config_path``.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, Any

from agentic_odi_connectors.catalog import (
    connector_config_from_preset,
    get_preset,
    list_presets,
)
from agentic_odi_connectors.factory import build_connector
from agentic_odi_connectors.models import ConnectorConfig, HealthStatus
from agentic_odi_connectors.paths import config_path
from agentic_odi_connectors.registry import ConnectorRegistry

if TYPE_CHECKING:
    from agentic_odi_studio_api.studio.marketplace import StudioMarketplace


class ConnectorService:
    """In-process management of the shared connector registry."""

    def __init__(
        self,
        path: Path | None = None,
        timeout: float = 15.0,
        marketplace: StudioMarketplace | None = None,
    ) -> None:
        self._path = path or config_path()
        self._timeout = timeout
        self._marketplace = marketplace

    def _registry(self) -> ConnectorRegistry:
        return ConnectorRegistry(self._path)

    def catalog(self) -> list[dict[str, Any]]:
        """Return all known presets (recommended first) as plain dicts."""
        return [preset.model_dump() for preset in list_presets()]

    def add(
        self,
        name: str | None = None,
        preset_id: str | None = None,
        url: str | None = None,
        marketplace_id: str | None = None,
    ) -> ConnectorConfig:
        """Register a connector from a preset, a marketplace listing, or a custom URL."""
        if marketplace_id is not None:
            if self._marketplace is None:
                raise ValueError("marketplace is not available in this sidecar")
            config = self._marketplace.config_for(marketplace_id)
            if name:
                config = config.model_copy(update={"name": name})
        elif preset_id is not None:
            preset = get_preset(preset_id)
            config = connector_config_from_preset(preset, name=name, url=url)
        elif url is not None:
            if not name:
                raise ValueError("name is required when registering a custom URL")
            config = ConnectorConfig(name=name, kind="mcp", settings={"url": url})
        else:
            raise ValueError("must provide preset_id, marketplace_id, or url")
        self._registry().add(config)
        return config

    def list(self) -> list[ConnectorConfig]:
        return self._registry().list_all()

    def delete(self, name: str) -> bool:
        return self._registry().delete(name)

    def health(self, name: str) -> HealthStatus:
        """Run a connector's health check with a bounded timeout."""
        connector = build_connector(self._registry().get(name))
        try:
            return asyncio.run(asyncio.wait_for(connector.health(), timeout=self._timeout))
        except Exception as exc:  # noqa: BLE001
            return HealthStatus(ok=False, message=f"unhealthy: {exc}", details={})

    __all__ = ["ConnectorService"]
