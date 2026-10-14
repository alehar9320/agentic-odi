"""Shared Pydantic models for connector configuration and ingest payloads."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from .errors import UnknownConnectorKindError


class HealthStatus(BaseModel):
    ok: bool
    detail: str = ""


class McpConnectorSettings(BaseModel):
    url: str
    tools: list[str] = Field(default_factory=list)


class ConnectorConfig(BaseModel):
    name: str
    kind: str = "mcp"
    enabled: bool = True
    settings: dict[str, Any] = Field(default_factory=dict)

    def mcp_settings(self) -> McpConnectorSettings:
        if self.kind != "mcp":
            raise UnknownConnectorKindError(name=self.kind)
        return McpConnectorSettings.model_validate(self.settings)


class IngestRecord(BaseModel):
    id: str
    source_name: str
    source_kind: str
    item_type: Literal["resource", "tool_result", "catalog"]
    name: str
    content: str
    raw: dict[str, Any] = Field(default_factory=dict)


class IngestBatch(BaseModel):
    connector_name: str
    records: list[IngestRecord] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
