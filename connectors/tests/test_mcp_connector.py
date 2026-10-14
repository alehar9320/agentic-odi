import pytest
from fastmcp import Client, FastMCP

from connectors import ConnectorConfig, IngestSink
from connectors.mcp import MCPClientConnector


def _server() -> FastMCP:
    server = FastMCP("external")

    @server.resource("config://greeting")
    def greeting() -> str:
        return "hello from remote"

    @server.tool
    def ping() -> str:
        return "pong"

    return server


def _connector(sink, tools=None, factory=None):
    cfg = ConnectorConfig(
        name="ext",
        kind="mcp",
        settings={"url": "http://unused/mcp", "tools": tools or []},
    )
    return MCPClientConnector(cfg, sink, client_factory=factory or (lambda: Client(_server())))


@pytest.mark.asyncio
async def test_health_ok_on_live_server():
    status = await _connector(IngestSink()).health()
    assert status.ok is True
    assert "1 tool" in status.detail


@pytest.mark.asyncio
async def test_ingest_yields_catalog_resource_and_tool_records():
    sink = IngestSink()
    batch = await _connector(sink, tools=["ping"]).ingest()
    kinds = {r.item_type for r in batch.records}
    assert kinds == {"catalog", "resource", "tool_result"}
    assert any(r.content == "hello from remote" for r in batch.records)
    assert any(r.content == "pong" for r in batch.records)
    assert batch.errors == []


@pytest.mark.asyncio
async def test_ingest_with_no_tools_configured():
    batch = await _connector(IngestSink()).ingest()
    assert not any(r.item_type == "tool_result" for r in batch.records)


@pytest.mark.asyncio
async def test_ingest_records_unknown_tool_as_error():
    batch = await _connector(IngestSink(), tools=["does_not_exist"]).ingest()
    assert batch.errors and any("does_not_exist" in e for e in batch.errors)
    assert any(r.item_type == "catalog" for r in batch.records)


class _BrokenClient:
    async def __aenter__(self):
        raise TimeoutError("connect timed out")

    async def __aexit__(self, *exc):
        return False


@pytest.mark.asyncio
async def test_health_fails_cleanly_on_dead_server():
    status = await _connector(IngestSink(), factory=lambda: _BrokenClient()).health()
    assert status.ok is False
    assert "timed out" in status.detail
