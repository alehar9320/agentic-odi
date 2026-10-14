from types import SimpleNamespace

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


class _PartialReadClient:
    """Fake client where one resource read fails and another succeeds."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def list_tools(self):
        return []

    async def list_resources(self):
        return [
            SimpleNamespace(name="broken", uri="config://broken"),
            SimpleNamespace(name="good", uri="config://good"),
        ]

    async def read_resource(self, uri):
        if uri == "config://broken":
            raise RuntimeError("resource read blew up")
        return [SimpleNamespace(text="good payload")]


@pytest.mark.asyncio
async def test_ingest_survives_resource_read_failure():
    batch = await _connector(IngestSink(), factory=lambda: _PartialReadClient()).ingest()

    kinds = [r.item_type for r in batch.records]
    assert "catalog" in kinds
    assert any(
        r.item_type == "resource" and r.name == "good" and r.content == "good payload"
        for r in batch.records
    )
    assert batch.errors and any("broken" in e for e in batch.errors)


@pytest.mark.asyncio
async def test_ingest_empty_server_yields_only_catalog():
    batch = await _connector(IngestSink(), factory=lambda: Client(FastMCP("empty"))).ingest()

    assert [r.item_type for r in batch.records] == ["catalog"]
    catalog = batch.records[0]
    assert catalog.content == '{"tools": [], "resources": []}'
    assert batch.errors == []
