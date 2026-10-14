"""MCP (Model Context Protocol) client connector built on ``fastmcp.Client``."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from fastmcp import Client

from .models import (
    ConnectorConfig,
    HealthStatus,
    IngestBatch,
    IngestRecord,
    McpConnectorSettings,
)
from .sink import IngestSink


class MCPClientConnector:
    """Ingests a catalog, resources and selected tool outputs from an MCP server."""

    kind = "mcp"

    def __init__(
        self,
        config: ConnectorConfig,
        sink: IngestSink,
        client_factory: Callable[[], Client] | None = None,
    ) -> None:
        self.name = config.name
        self.settings: McpConnectorSettings = config.mcp_settings()
        self._sink = sink
        if client_factory is None:
            self._client_factory: Callable[[], Client] = lambda: Client(self.settings.url)
        else:
            self._client_factory = client_factory

    async def health(self) -> HealthStatus:
        try:
            async with self._client_factory() as client:
                tools = await client.list_tools()
        except Exception as exc:  # noqa: BLE001 - health must never raise
            return HealthStatus(ok=False, detail=str(exc))
        count = len(tools) if tools is not None else 0
        return HealthStatus(ok=True, detail=f"{count} tool(s) available")

    async def ingest(self) -> IngestBatch:
        batch = IngestBatch(connector_name=self.name)
        async with self._client_factory() as client:
            tools = await client.list_tools()
            resources = await client.list_resources()

            tool_names = [tool.name for tool in tools] if tools else []
            resource_list = list(resources) if resources else []
            resource_names = [res.name for res in resource_list]

            batch.records.append(
                IngestRecord(
                    id=f"{self.name}:catalog",
                    source_name=self.name,
                    source_kind=self.kind,
                    item_type="catalog",
                    name="catalog",
                    content=json.dumps({"tools": tool_names, "resources": resource_names}),
                    raw={
                        "tools": tool_names,
                        "resources": [
                            {"name": res.name, "uri": str(getattr(res, "uri", ""))}
                            for res in resource_list
                        ],
                    },
                )
            )

            for res in resource_list:
                uri = str(getattr(res, "uri", ""))
                try:
                    blocks = await client.read_resource(uri)
                    for block in blocks or []:
                        text = getattr(block, "text", None)
                        batch.records.append(
                            IngestRecord(
                                id=f"{self.name}:resource:{res.name}",
                                source_name=self.name,
                                source_kind=self.kind,
                                item_type="resource",
                                name=res.name,
                                content=text if text is not None else str(block),
                                raw={"uri": uri},
                            )
                        )
                except Exception as exc:  # noqa: BLE001 - collect, never abort
                    batch.errors.append(f"resource {res.name}: {exc}")

            for tool_name in self.settings.tools:
                try:
                    result = await client.call_tool(tool_name, {})
                    batch.records.append(
                        IngestRecord(
                            id=f"{self.name}:tool:{tool_name}",
                            source_name=self.name,
                            source_kind=self.kind,
                            item_type="tool_result",
                            name=tool_name,
                            content=_tool_result_text(result),
                            raw={},
                        )
                    )
                except Exception as exc:  # noqa: BLE001 - collect, never abort
                    batch.errors.append(f"tool {tool_name}: {exc}")

        self._sink.append(batch)
        return batch


def _tool_result_text(result: Any) -> str:
    blocks = getattr(result, "content", None)
    if blocks:
        parts: list[str] = []
        for block in blocks:
            text = getattr(block, "text", None)
            if text is not None:
                parts.append(text)
            else:
                data = getattr(block, "data", None)
                parts.append(str(data) if data is not None else str(block))
        return "".join(parts)
    data = getattr(result, "data", None)
    return str(data) if data is not None else ""


__all__ = ["MCPClientConnector"]
