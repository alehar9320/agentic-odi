"""JSON-backed registry of named connector configurations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agentic_odi_connectors.models import ConnectorConfig


class UnknownConnectorKindError(ValueError):
    def __init__(self, kind: str) -> None:
        self.kind = kind
        super().__init__(f"Unknown connector kind: {kind}")


class DuplicateConnectorError(ValueError):
    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"Connector already exists: {name}")


class ConnectorNotFoundError(ValueError):
    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"Connector not found: {name}")


def _known_kinds() -> set[str]:
    from agentic_odi_connectors.factory import known_kinds

    return known_kinds()


class ConnectorRegistry:
    """Persists connector configs to a JSON file."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def add(self, config: ConnectorConfig) -> None:
        if config.kind not in _known_kinds():
            raise UnknownConnectorKindError(config.kind)
        connectors = self._load()
        if any(existing.name == config.name for existing in connectors):
            raise DuplicateConnectorError(config.name)
        connectors.append(config)
        self._save(connectors)

    def list_all(self) -> list[ConnectorConfig]:
        return self._load()

    def get(self, name: str) -> ConnectorConfig:
        for config in self._load():
            if config.name == name:
                return config
        raise ConnectorNotFoundError(name)

    def _load(self) -> list[ConnectorConfig]:
        if not self.path.exists():
            return []
        with self.path.open(encoding="utf-8") as handle:
            payload: dict[str, Any] = json.load(handle)
        raw_connectors = payload.get("connectors", [])
        return [ConnectorConfig.model_validate(item) for item in raw_connectors]

    def _save(self, connectors: list[ConnectorConfig]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"connectors": [item.model_dump(mode="json") for item in connectors]}
        with self.path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
            handle.write("\n")
