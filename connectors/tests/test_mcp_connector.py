from unittest.mock import MagicMock

import pytest
from fastmcp import FastMCP

from connectors.mcp.connector import MCPClientConnector
from connectors.models import McpConnectorSettings


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
        tools=list(overrides.pop("tools", [])),  # type: ignore[arg-type]
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
