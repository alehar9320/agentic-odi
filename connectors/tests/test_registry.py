from pathlib import Path

import pytest

from connectors.models import ConnectorConfig
from connectors.registry import (
    ConnectorNotFoundError,
    ConnectorRegistry,
    DuplicateConnectorError,
    UnknownConnectorKindError,
)


def _registry(tmp_path: Path) -> ConnectorRegistry:
    return ConnectorRegistry(tmp_path / "connectors.json")


def test_add_persists_connector(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    config = ConnectorConfig(
        name="gong",
        kind="mcp",
        settings={"url": "http://localhost:9000/mcp"},
    )

    registry.add(config)

    stored = registry.list()
    assert len(stored) == 1
    assert stored[0].name == "gong"
    assert stored[0].kind == "mcp"
    assert stored[0].settings["url"] == "http://localhost:9000/mcp"


def test_list_returns_added_connectors(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    registry.add(
        ConnectorConfig(name="one", kind="mcp", settings={"url": "http://localhost:1/mcp"})
    )
    registry.add(
        ConnectorConfig(name="two", kind="mcp", settings={"url": "http://localhost:2/mcp"})
    )

    names = {item.name for item in registry.list()}

    assert names == {"one", "two"}


def test_add_rejects_duplicate_name(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    config = ConnectorConfig(name="gong", kind="mcp", settings={"url": "http://localhost:1/mcp"})
    registry.add(config)

    with pytest.raises(DuplicateConnectorError):
        registry.add(config)


def test_add_rejects_unknown_kind(tmp_path: Path) -> None:
    registry = _registry(tmp_path)

    with pytest.raises(UnknownConnectorKindError) as exc_info:
        registry.add(ConnectorConfig(name="jira", kind="rest", settings={}))

    assert exc_info.value.kind == "rest"


def test_get_returns_matching_connector(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    registry.add(
        ConnectorConfig(name="gong", kind="mcp", settings={"url": "http://localhost:1/mcp"})
    )

    found = registry.get("gong")

    assert found.name == "gong"


def test_get_missing_raises(tmp_path: Path) -> None:
    registry = _registry(tmp_path)

    with pytest.raises(ConnectorNotFoundError):
        registry.get("missing")


def test_load_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "connectors.json"
    first = ConnectorRegistry(path)
    first.add(ConnectorConfig(name="gong", kind="mcp", settings={"url": "http://localhost:1/mcp"}))

    second = ConnectorRegistry(path)
    loaded = second.list()

    assert len(loaded) == 1
    assert loaded[0].name == "gong"
