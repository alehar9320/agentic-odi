import pytest

from connectors import ConnectorConfig, ConnectorRegistry
from connectors.errors import (
    ConnectorNotFoundError,
    DuplicateConnectorError,
    RegistryError,
)


def _reg(tmp_path):
    return ConnectorRegistry(path=tmp_path / "connectors.json")


def test_add_then_list_roundtrips(tmp_path):
    reg = _reg(tmp_path)
    reg.add(ConnectorConfig(name="gong", kind="mcp", settings={"url": "http://h/mcp"}))
    assert [c.name for c in reg.list()] == ["gong"]


def test_config_persists_across_instances(tmp_path):
    p = tmp_path / "connectors.json"
    ConnectorRegistry(path=p).add(ConnectorConfig(name="a", settings={"url": "http://h/mcp"}))
    assert ConnectorRegistry(path=p).get("a").settings["url"] == "http://h/mcp"


def test_list_missing_file_returns_empty(tmp_path):
    assert _reg(tmp_path).list() == []


def test_duplicate_name_rejected(tmp_path):
    reg = _reg(tmp_path)
    reg.add(ConnectorConfig(name="a", settings={"url": "http://h/mcp"}))
    with pytest.raises(DuplicateConnectorError):
        reg.add(ConnectorConfig(name="a", settings={"url": "http://h/mcp"}))


def test_get_unknown_name_raises(tmp_path):
    with pytest.raises(ConnectorNotFoundError):
        _reg(tmp_path).get("nope")


def test_malformed_json_raises_registry_error(tmp_path):
    p = tmp_path / "connectors.json"
    p.write_text("{not json")
    with pytest.raises(RegistryError):
        ConnectorRegistry(path=p).list()


def test_build_connector_rejects_unknown_kind(tmp_path):
    from connectors import IngestSink
    from connectors.errors import UnknownConnectorKindError
    from connectors.registry import build_connector

    cfg = ConnectorConfig(name="x", kind="rest", settings={})
    with pytest.raises(UnknownConnectorKindError):
        build_connector(cfg, IngestSink())
