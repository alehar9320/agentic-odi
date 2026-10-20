from unittest.mock import MagicMock

import pytest
from agentic_odi_connectors.mcp.connector import MCPClientConnector, MissingEnvironmentError
from agentic_odi_connectors.models import McpConnectorSettings
from fastmcp import FastMCP
from fastmcp.client.transports import StreamableHttpTransport


def _external_server() -> FastMCP:
    server = FastMCP("External Source")

    @server.resource("resource://sample-feedback")
    def sample_feedback() -> str:
        return "Secrets deployment broke staging"

    @server.tool
    def latest_quote() -> str:
        """Return the latest customer quote."""
        return "Lost 2 hours on deploy"

    return server


def _connector(**overrides: object) -> MCPClientConnector:
    settings = McpConnectorSettings(
        url="http://unused.example/mcp",
        tools=list(overrides.pop("tools", [])),  # type: ignore[call-overload]
    )
    return MCPClientConnector(
        name="gong",
        settings=settings,
        server=_external_server(),
    )


@pytest.mark.asyncio
async def test_health_succeeds_against_in_memory_server() -> None:
    status = await _connector().health()

    assert status.ok is True
    assert status.message == "reachable"


@pytest.mark.asyncio
async def test_health_reports_tool_and_resource_counts() -> None:
    status = await _connector().health()

    assert status.details["tool_count"] == 1
    assert status.details["resource_count"] == 1


@pytest.mark.asyncio
async def test_ingest_includes_catalog_record() -> None:
    batch = await _connector().ingest()

    catalog = next(record for record in batch.records if record.item_type == "catalog")
    assert catalog.source_name == "gong"
    assert catalog.source_kind == "mcp"
    assert "latest_quote" in catalog.content


@pytest.mark.asyncio
async def test_ingest_includes_resource_record() -> None:
    batch = await _connector().ingest()

    resource = next(record for record in batch.records if record.item_type == "resource")
    assert "Secrets deployment broke staging" in resource.content
    assert resource.source_name == "gong"


@pytest.mark.asyncio
async def test_ingest_calls_configured_tools() -> None:
    batch = await _connector(tools=["latest_quote"]).ingest()

    tool_result = next(record for record in batch.records if record.item_type == "tool_result")
    assert tool_result.name == "latest_quote"
    assert "Lost 2 hours on deploy" in tool_result.content
    assert batch.errors == []


@pytest.mark.asyncio
async def test_ingest_records_error_for_missing_tool() -> None:
    batch = await _connector(tools=["missing_tool"]).ingest()

    assert any("missing_tool" in error for error in batch.errors)
    assert not any(record.item_type == "tool_result" for record in batch.records)


@pytest.mark.asyncio
async def test_health_fails_when_client_raises() -> None:
    connector = _connector()
    boom = MagicMock()
    boom.side_effect = ConnectionError("refused")
    connector._client = boom  # type: ignore[method-assign]

    status = await connector.health()

    assert status.ok is False
    assert "refused" in status.message


def _http_connector(settings: McpConnectorSettings) -> MCPClientConnector:
    return MCPClientConnector(name="preset", settings=settings)


def test_transport_expands_url_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-123")
    connector = _http_connector(
        McpConnectorSettings(
            url="https://mcp.tavily.com/mcp/?tavilyApiKey=${TAVILY_API_KEY}",
            env_vars=["TAVILY_API_KEY"],
        )
    )

    transport = connector.transport()

    assert isinstance(transport, StreamableHttpTransport)
    assert str(transport.url) == "https://mcp.tavily.com/mcp/?tavilyApiKey=tvly-123"


def test_transport_expands_headers_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_PERSONAL_ACCESS_TOKEN", "ghp_example")
    connector = _http_connector(
        McpConnectorSettings(
            url="https://api.githubcopilot.com/mcp/",
            env_vars=["GITHUB_PERSONAL_ACCESS_TOKEN"],
            headers={"Authorization": "Bearer ${GITHUB_PERSONAL_ACCESS_TOKEN}"},
        )
    )

    transport = connector.transport()

    assert isinstance(transport, StreamableHttpTransport)
    assert transport.headers == {"Authorization": "Bearer ghp_example"}


def test_transport_requests_oauth_when_configured() -> None:
    connector = _http_connector(
        McpConnectorSettings(url="https://mcp.notion.com/mcp", auth="oauth")
    )

    transport = connector.transport()

    assert isinstance(transport, StreamableHttpTransport)
    assert transport.auth is not None


def test_transport_requires_declared_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    connector = _http_connector(
        McpConnectorSettings(
            url="https://mcp.exa.ai/mcp?exaApiKey=${EXA_API_KEY}",
            env_vars=["EXA_API_KEY"],
        )
    )

    with pytest.raises(MissingEnvironmentError) as exc_info:
        connector.transport()

    assert exc_info.value.names == ["EXA_API_KEY"]
    assert "EXA_API_KEY" in str(exc_info.value)


@pytest.mark.asyncio
async def test_health_reports_missing_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    connector = _http_connector(
        McpConnectorSettings(
            url="https://mcp.exa.ai/mcp?exaApiKey=${EXA_API_KEY}",
            env_vars=["EXA_API_KEY"],
        )
    )

    status = await connector.health()

    assert status.ok is False
    assert "EXA_API_KEY" in status.message
    assert status.details["missing_env"] == ["EXA_API_KEY"]


@pytest.mark.asyncio
async def test_ingest_reports_missing_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    connector = _http_connector(
        McpConnectorSettings(
            url="https://mcp.exa.ai/mcp?exaApiKey=${EXA_API_KEY}",
            env_vars=["EXA_API_KEY"],
        )
    )

    batch = await connector.ingest()

    assert any("EXA_API_KEY" in error for error in batch.errors)
    assert batch.records == []
