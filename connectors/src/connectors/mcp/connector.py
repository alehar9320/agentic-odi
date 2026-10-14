"""MCP client connector that ingests tools and resources from an external server."""

from __future__ import annotations

import json
from typing import Any

from fastmcp import Client, FastMCP

from connectors.models import (
    HealthStatus,
    IngestBatch,
    IngestRecord,
    McpConnectorSettings,
)
from connectors.protocol import Connector


def _to_dict(obj: Any) -> dict[str, Any]:
    if hasattr(obj, "model_dump"):
        dumped = obj.model_dump(mode="json")
        if isinstance(dumped, dict):
            return dumped
    return {"repr": repr(obj)}


def _content_text(obj: Any) -> str:
    parts: list[str] = []
    content = getattr(obj, "content", None)
    if content is None:
        text = getattr(obj, "text", None)
        return text if isinstance(text, str) else json.dumps(_to_dict(obj))
    for item in content:
        text = getattr(item, "text", None)
        if isinstance(text, str):
            parts.append(text)
    return "\n".join(parts) if parts else json.dumps(_to_dict(obj))


class MCPClientConnector(Connector):
    """Pulls catalog, resources, and optional tool results from an MCP server."""

    kind = "mcp"

    def __init__(
        self,
        name: str,
        settings: McpConnectorSettings,
        *,
        server: FastMCP | None = None,
    ) -> None:
        self.name = name
        self.settings = settings
        self._server = server

    def _client(self) -> Client:
        if self._server is not None:
            return Client(self._server)
        return Client(self.settings.url)

    async def health(self) -> HealthStatus:
        try:
            async with self._client() as client:
                await client.ping()
                tools = await client.list_tools()
                resources = await client.list_resources()
            return HealthStatus(
                ok=True,
                message="reachable",
                details={
                    "tool_count": len(tools),
                    "resource_count": len(resources),
                },
            )
        except Exception as exc:
            return HealthStatus(ok=False, message=str(exc))

    async def ingest(self) -> IngestBatch:
        batch = IngestBatch(connector_name=self.name)
        try:
            async with self._client() as client:
                tools = await client.list_tools()
                resources = await client.list_resources()
                tool_dicts = [_to_dict(tool) for tool in tools]
                resource_dicts = [_to_dict(resource) for resource in resources]
                catalog_raw = {"tools": tool_dicts, "resources": resource_dicts}
                batch.records.append(
                    IngestRecord(
                        source_name=self.name,
                        source_kind=self.kind,
                        item_type="catalog",
                        name="mcp-catalog",
                        content=json.dumps(catalog_raw, indent=2),
                        raw=catalog_raw,
                    )
                )
                for resource in resources:
                    uri = str(getattr(resource, "uri", ""))
                    name = str(getattr(resource, "name", None) or uri)
                    try:
                        contents = await client.read_resource(uri)
                        content_text = "\n".join(
                            getattr(item, "text", "") or "" for item in contents
                        )
                        batch.records.append(
                            IngestRecord(
                                source_name=self.name,
                                source_kind=self.kind,
                                item_type="resource",
                                name=name,
                                content=content_text,
                                raw={"uri": uri, "resource": _to_dict(resource)},
                            )
                        )
                    except Exception as exc:
                        batch.errors.append(f"Failed to read resource {uri}: {exc}")
                configured_tools = self.settings.tools
                available = {str(getattr(tool, "name", "")) for tool in tools}
                for tool_name in configured_tools:
                    if tool_name not in available:
                        batch.errors.append(f"Tool not found: {tool_name}")
                        continue
                    try:
                        result = await client.call_tool(tool_name, {})
                        batch.records.append(
                            IngestRecord(
                                source_name=self.name,
                                source_kind=self.kind,
                                item_type="tool_result",
                                name=tool_name,
                                content=_content_text(result),
                                raw={"tool": tool_name, "result": _to_dict(result)},
                            )
                        )
                    except Exception as exc:
                        batch.errors.append(f"Failed to call tool {tool_name}: {exc}")
        except Exception as exc:
            batch.errors.append(str(exc))
        return batch
