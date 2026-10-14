"""CLI adapter for listing, adding, checking, and ingesting external connectors."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Optional

import typer

from connectors.factory import build_connector
from connectors.models import ConnectorConfig
from connectors.registry import (
    ConnectorNotFoundError,
    ConnectorRegistry,
    DuplicateConnectorError,
    UnknownConnectorKindError,
)
from connectors.sink import get_default_sink

connectors_app = typer.Typer(
    name="connectors",
    help="Connect Agentic ODI to external systems.",
    no_args_is_help=True,
)


def _config_path(config: Path | None) -> Path:
    if config is not None:
        return config
    env = os.getenv("AGENTIC_ODI_CONNECTORS_FILE")
    if env:
        return Path(env)
    return Path.cwd() / ".agentic-odi" / "connectors.json"


def _registry(config: Path | None) -> ConnectorRegistry:
    return ConnectorRegistry(_config_path(config))


ConfigOption = typer.Option(
    None,
    "--config",
    help="Path to the connectors JSON registry.",
    envvar="AGENTIC_ODI_CONNECTORS_FILE",
)


@connectors_app.command("list")
def list_connectors(
    config: Optional[Path] = ConfigOption,
) -> None:
    """List configured external connectors."""
    items = _registry(config).list()
    if not items:
        typer.echo("No connectors configured.")
        return
    for item in items:
        status = "enabled" if item.enabled else "disabled"
        typer.echo(f"{item.name}\t{item.kind}\t{status}")


@connectors_app.command("add")
def add_connector(
    kind: str = typer.Argument(..., help="Connector kind (currently: mcp)."),
    name: str = typer.Option(..., "--name", help="Unique connector name."),
    url: Optional[str] = typer.Option(None, "--url", help="MCP server URL (required for kind mcp)."),
    tool: Optional[list[str]] = typer.Option(
        None,
        "--tool",
        help="MCP tool to call during ingest. Repeatable.",
    ),
    config: Optional[Path] = ConfigOption,
) -> None:
    """Register a new external connector."""
    settings: dict[str, object] = {}
    if kind == "mcp":
        if not url:
            typer.echo("Error: --url is required for MCP connectors.", err=True)
            raise typer.Exit(code=1)
        settings["url"] = url
        if tool:
            settings["tools"] = tool
    connector_config = ConnectorConfig(name=name, kind=kind, settings=settings)
    try:
        _registry(config).add(connector_config)
    except DuplicateConnectorError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    except UnknownConnectorKindError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Added {kind} connector '{name}'.")


@connectors_app.command("health")
def health_connector(
    name: str = typer.Option(..., "--name", help="Connector name."),
    config: Optional[Path] = ConfigOption,
) -> None:
    """Check whether a connector can reach its external system."""
    try:
        connector_config = _registry(config).get(name)
        connector = build_connector(connector_config)
    except (ConnectorNotFoundError, UnknownConnectorKindError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    status = asyncio.run(connector.health())
    typer.echo(status.model_dump_json())
    if not status.ok:
        raise typer.Exit(code=1)


@connectors_app.command("ingest")
def ingest_connector(
    name: str = typer.Option(..., "--name", help="Connector name."),
    config: Optional[Path] = ConfigOption,
) -> None:
    """Ingest data from an external connector into the local ingest sink."""
    try:
        connector_config = _registry(config).get(name)
        connector = build_connector(connector_config)
    except (ConnectorNotFoundError, UnknownConnectorKindError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    batch = asyncio.run(connector.ingest())
    get_default_sink().append(batch)
    typer.echo(batch.model_dump_json())
