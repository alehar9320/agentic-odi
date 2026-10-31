"""Shared Pydantic models for external connectors and ingest records."""

from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field


class ConfigurationError(ValueError):
    """Raised when a connector configuration fails validation.

    Attributes:
        keys: The missing or invalid config keys, used to surface which
            fields need correction at startup.
    """

    def __init__(self, keys: list[str]) -> None:
        self.keys = keys
        joined = ", ".join(keys)
        super().__init__(f"Invalid connector config: {joined}")


ItemType = Literal["resource", "tool_result", "catalog"]
McpAuthMode = Literal["none", "oauth"]
EvidenceItemType = Literal["catalog", "resource", "tool_result", "manual", "note"]


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
    """Connection details for an MCP server.

    ``url`` and ``headers`` may interpolate environment variables with
    ``${VAR}`` so registry files never hold tokens. ``env_vars`` names the
    variables that must be present before connecting.
    """

    url: str
    tools: list[str] = Field(default_factory=list)
    auth: McpAuthMode = "none"
    headers: dict[str, str] = Field(default_factory=dict)
    env_vars: list[str] = Field(default_factory=list)
    tool_args: dict[str, dict] = Field(
        default_factory=dict,
        description="Per-tool argument overrides passed to call_tool.",
    )


class PaginationSettings(BaseModel):
    """Opt-in paging: where to find the next page, relative to the response."""

    next_path: str = Field(
        ..., description="Dotted path to the next page URL or cursor in the response."
    )


class RestConnectorSettings(BaseModel):
    url: str
    method: Literal["GET", "POST"] = "GET"
    headers: dict[str, str] = Field(default_factory=dict)
    json_body: dict[str, Any] | None = None
    records_key: str | None = None
    timeout: float = 10.0
    item_type: ItemType = "resource"
    pagination: PaginationSettings | None = None


class ConnectorConfig(BaseModel):
    name: str
    kind: str
    enabled: bool = True
    settings: dict[str, Any] = Field(default_factory=dict)
