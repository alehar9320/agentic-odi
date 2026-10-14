import pytest

from connectors.factory import build_connector, known_kinds, register_kind
from connectors.mcp.connector import MCPClientConnector
from connectors.models import ConnectorConfig, HealthStatus, IngestBatch
from connectors.protocol import Connector
from connectors.registry import UnknownConnectorKindError


class _StubConnector(Connector):
    kind = "stub"
    name = "stub"

    async def health(self) -> HealthStatus:
        return HealthStatus(ok=True, message="ok")

    async def ingest(self) -> IngestBatch:
        return IngestBatch(connector_name=self.name)


def test_build_mcp_connector() -> None:
    config = ConnectorConfig(
        name="gong",
        kind="mcp",
        settings={"url": "http://localhost:9000/mcp"},
    )

    connector = build_connector(config)

    assert isinstance(connector, MCPClientConnector)
    assert connector.name == "gong"
    assert connector.settings.url == "http://localhost:9000/mcp"


def test_build_unknown_kind_raises() -> None:
    config = ConnectorConfig(name="jira", kind="rest", settings={})

    with pytest.raises(UnknownConnectorKindError):
        build_connector(config)


def test_register_kind_is_used() -> None:
    def build_stub(config: ConnectorConfig) -> Connector:
        stub = _StubConnector()
        stub.name = config.name
        return stub

    register_kind("stub", build_stub)
    try:
        connector = build_connector(ConnectorConfig(name="demo", kind="stub", settings={}))
        assert isinstance(connector, _StubConnector)
        assert connector.name == "demo"
        assert "stub" in known_kinds()
    finally:
        from connectors import factory

        factory._builders.pop("stub", None)
