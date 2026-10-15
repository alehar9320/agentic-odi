"""JSON-backed connection registry plus the connector kind dispatcher."""

from __future__ import annotations

import builtins
import json
import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field, ValidationError

from .errors import (
    ConnectorNotFoundError,
    DuplicateConnectorError,
    RegistryError,
    UnknownConnectorKindError,
)
from .models import ConnectorConfig

if TYPE_CHECKING:
    from .protocol import Connector
    from .sink import IngestSink


class _RegistryFile(BaseModel):
    connectors: list[ConnectorConfig] = Field(default_factory=list)


class ConnectorRegistry:
    """Reads and writes connector configurations from a JSON file."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = (
            Path(path) if path is not None else Path.cwd() / ".agentic-odi" / "connectors.json"
        )

    def list(self) -> list[ConnectorConfig]:
        if not self.path.exists():
            return []
        try:
            raw = json.loads(self.path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise RegistryError(f"failed to read registry {self.path}: {exc}") from exc
        try:
            return _RegistryFile.model_validate(raw).connectors
        except ValidationError as exc:
            raise RegistryError(f"invalid registry {self.path}: {exc}") from exc

    def get(self, name: str) -> ConnectorConfig:
        for config in self.list():
            if config.name == name:
                return config
        raise ConnectorNotFoundError(f"connector {name!r} not found in {self.path}")

    def add(self, config: ConnectorConfig) -> None:
        configs = self.list()
        if any(existing.name == config.name for existing in configs):
            raise DuplicateConnectorError(f"connector {config.name!r} already exists")
        configs.append(config)
        self.save(configs)

    def save(self, configs: builtins.list[ConnectorConfig]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = _RegistryFile(connectors=configs).model_dump()
        fd, tmp_name = tempfile.mkstemp(dir=self.path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as tmp_file:
                json.dump(payload, tmp_file)
            os.replace(tmp_name, self.path)
        except BaseException:
            Path(tmp_name).unlink(missing_ok=True)
            raise


def build_connector(
    config: ConnectorConfig,
    sink: IngestSink,
    client_factory: Any = None,
) -> Connector:
    """Construct a connector for the given config's kind."""
    if config.kind == "mcp":
        from .mcp import MCPClientConnector

        return MCPClientConnector(config, sink, client_factory=client_factory)
    raise UnknownConnectorKindError(config.kind)
