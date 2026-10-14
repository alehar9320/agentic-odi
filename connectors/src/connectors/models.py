"""Shared Pydantic models for external connectors and ingest records."""

from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field

ItemType = Literal["resource", "tool_result", "catalog"]


class HealthStatus(BaseModel):
    ok: bool
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class IngestRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_name: str
    source_kind: str
    item_type: ItemType
    name: str
    content: str
    raw: dict[str, Any] = Field(default_factory=dict)


class IngestBatch(BaseModel):
    connector_name: str
    records: list[IngestRecord] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class McpConnectorSettings(BaseModel):
    url: str
    tools: list[str] = Field(default_factory=list)


class ConnectorConfig(BaseModel):
    name: str
    kind: str
    enabled: bool = True
    settings: dict[str, Any] = Field(default_factory=dict)
