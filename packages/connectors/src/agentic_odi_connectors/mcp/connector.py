"""MCP client connector that ingests tools and resources from an external server."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping
from typing import Any

from fastmcp import Client, FastMCP
from fastmcp.client.transports import StreamableHttpTransport

from agentic_odi_connectors.models import (
    HealthStatus,
    IngestBatch,
    IngestRecord,
    McpConnectorSettings,
)
from agentic_odi_connectors.protocol import Connector

_ENV_VAR_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


class MissingEnvironmentError(RuntimeError):
    """Raised when a connector needs credentials that are not in the environment."""

    def __init__(self, names: list[str]) -> None:
        self.names = names
        super().__init__("Missing environment variable(s): " + ", ".join(names))


def _expand_env(value: str, environ: Mapping[str, str]) -> str:
    return _ENV_VAR_PATTERN.sub(lambda match: environ.get(match.group(1), ""), value)


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

    def transport(self) -> StreamableHttpTransport | FastMCP:
        """Build the MCP transport, resolving credentials from the environment."""
        if self._server is not None:
            return self._server
        missing = sorted(name for name in self.settings.env_vars if not os.environ.get(name))
        if missing:
            raise MissingEnvironmentError(missing)
        headers = {
            key: _expand_env(value, os.environ) for key, value in self.settings.headers.items()
        }
        return StreamableHttpTransport(
            url=_expand_env(self.settings.url, os.environ),
            headers=headers or None,
            auth="oauth" if self.settings.auth == "oauth" else None,
        )

    def _client(self) -> Client:
        return Client(self.transport())

    async def health(self) -> HealthStatus:
        try:
            async with self._client() as client:
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
        except MissingEnvironmentError as exc:
            return HealthStatus(
                ok=False,
                message=str(exc),
                details={"missing_env": exc.names},
            )
        except Exception as exc:  # noqa: BLE001
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
                    except Exception as exc:  # noqa: BLE001
                        batch.errors.append(f"Failed to read resource {uri}: {exc}")
                configured_tools = self.settings.tools
                available = {str(getattr(tool, "name", "")) for tool in tools}
                for tool_name in configured_tools:
                    if tool_name not in available:
                        batch.errors.append(f"Tool not found: {tool_name}")
                        continue
                    try:
                        result = await client.call_tool(
                            tool_name, self.settings.tool_args.get(tool_name, {})
                        )
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
                    except Exception as exc:  # noqa: BLE001
                        batch.errors.append(f"Failed to call tool {tool_name}: {exc}")
        except Exception as exc:  # noqa: BLE001
            batch.errors.append(str(exc))
        return batch
