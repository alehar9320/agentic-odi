import pytest
from agentic_odi_connectors.factory import build_connector, known_kinds, register_kind
from agentic_odi_connectors.mcp.connector import MCPClientConnector
from agentic_odi_connectors.models import ConnectorConfig, HealthStatus, IngestBatch
from agentic_odi_connectors.protocol import Connector
from agentic_odi_connectors.registry import UnknownConnectorKindError
from agentic_odi_connectors.rest.connector import RestConnector, WebhookConnector


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


def test_build_rest_connector() -> None:
    config = ConnectorConfig(
        name="jira", kind="rest", settings={"url": "https://jira.example/api/issues"}
    )

    connector = build_connector(config)

    assert isinstance(connector, RestConnector)
    assert connector.kind == "rest"
    assert connector.settings.url == "https://jira.example/api/issues"


def test_build_webhook_connector() -> None:
    config = ConnectorConfig(
        name="feedback", kind="webhook", settings={"url": "https://hooks.example/inbox"}
    )

    connector = build_connector(config)

    assert isinstance(connector, WebhookConnector)
    assert connector.kind == "webhook"


def test_build_unknown_kind_raises() -> None:
    config = ConnectorConfig(name="jira", kind="salesforce", settings={})

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
        from agentic_odi_connectors import factory

        factory._builders.pop("stub", None)
