"""CLI adapter for listing, adding, checking, and ingesting external connectors."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import TYPE_CHECKING

import typer

# The connectors package eagerly imports fastmcp via ``connectors/__init__``.
# Import it lazily so that merely loading the CLI (e.g. ``odi --version``) does
# not pay the fastmcp/mcp import cost. The wrappers below keep stable module
# attributes for tests to monkeypatch.
if TYPE_CHECKING:
    from connectors.models import ConnectorConfig
    from connectors.protocol import Connector
    from connectors.registry import ConnectorRegistry
    from connectors.sink import IngestSink

connectors_app = typer.Typer(
    name="connectors",
    help="Connect Agentic ODI to external systems.",
    no_args_is_help=True,
)


def build_connector(config: ConnectorConfig) -> Connector:
    from connectors.factory import build_connector as _build_connector

    return _build_connector(config)


def get_default_sink() -> IngestSink:
    from connectors.sink import get_default_sink as _get_default_sink

    return _get_default_sink()


def _config_path(config: Path | None) -> Path:
    if config is not None:
        return config
    env = os.getenv("AGENTIC_ODI_CONNECTORS_FILE")
    if env:
        return Path(env)
    return Path.cwd() / ".agentic-odi" / "connectors.json"


def _registry(config: Path | None) -> ConnectorRegistry:
    from connectors.registry import ConnectorRegistry

    return ConnectorRegistry(_config_path(config))


ConfigOption = typer.Option(
    None,
    "--config",
    help="Path to the connectors JSON registry.",
    envvar="AGENTIC_ODI_CONNECTORS_FILE",
)


@connectors_app.command("list")
def list_connectors(
    config: Path | None = ConfigOption,
) -> None:
    """List configured external connectors."""
    items = _registry(config).list_all()
    if not items:
        typer.echo("No connectors configured.")
        return
    for item in items:
        status = "enabled" if item.enabled else "disabled"
        typer.echo(f"{item.name}\t{item.kind}\t{status}")


@connectors_app.command("catalog")
def catalog_presets(
    area: str | None = typer.Option(None, "--area", help="Filter by capability area."),
    as_json: bool = typer.Option(False, "--json", help="Emit JSON instead of a table."),
) -> None:
    """Browse ready-to-use MCP server presets for common ODI workflows."""
    from connectors.catalog import AREA_LABELS, UnknownAreaError, list_presets

    try:
        presets = list_presets(area)
    except UnknownAreaError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    if as_json:
        typer.echo(json.dumps([preset.model_dump() for preset in presets], indent=2))
        return
    current_area: str | None = None
    for preset in presets:
        if preset.area != current_area:
            if current_area is not None:
                typer.echo()
            current_area = preset.area
            typer.echo(f"{AREA_LABELS[preset.area]} ({preset.area})")
        if preset.auth == "oauth":
            auth = "oauth"
        elif preset.env_vars:
            auth = "api key"
        else:
            auth = "none"
        line = f"  {preset.id:<12} {preset.label:<22} {auth:<8} {preset.url}"
        if preset.env_vars:
            line += f"  [{', '.join(preset.env_vars)}]"
        typer.echo(line)
    typer.echo("\nAdd one with: agentic-odi connectors add mcp --preset <id>")


def _mcp_connector_config(
    *,
    name: str | None,
    url: str | None,
    preset_id: str | None,
    tools: list[str] | None,
) -> ConnectorConfig:
    from connectors.catalog import (
        UnknownPresetError,
        connector_config_from_preset,
        get_preset,
    )
    from connectors.models import ConnectorConfig

    if preset_id is not None:
        try:
            preset = get_preset(preset_id)
        except UnknownPresetError as exc:
            typer.echo(f"Error: {exc}", err=True)
            raise typer.Exit(code=1) from exc
        return connector_config_from_preset(preset, name=name, url=url, tools=tools)
    if not url:
        typer.echo("Error: --url is required for MCP connectors (or pass --preset).", err=True)
        raise typer.Exit(code=1)
    if not name:
        typer.echo("Error: --name is required for MCP connectors.", err=True)
        raise typer.Exit(code=1)
    settings: dict[str, object] = {"url": url}
    if tools:
        settings["tools"] = tools
    return ConnectorConfig(name=name, kind="mcp", settings=settings)


@connectors_app.command("add")
def add_connector(
    kind: str = typer.Argument(..., help="Connector kind (currently: mcp)."),
    name: str | None = typer.Option(
        None, "--name", help="Unique connector name (defaults to the preset id)."
    ),
    url: str | None = typer.Option(
        None, "--url", help="MCP server URL (required for kind mcp unless --preset is given)."
    ),
    preset: str | None = typer.Option(
        None, "--preset", help="Preset id from 'connectors catalog'."
    ),
    tool: list[str] | None = typer.Option(  # noqa: B008
        None,
        "--tool",
        help="MCP tool to call during ingest. Repeatable.",
    ),
    config: Path | None = ConfigOption,
) -> None:
    """Register a new external connector, optionally from a known preset."""
    from connectors.models import ConnectorConfig
    from connectors.registry import DuplicateConnectorError, UnknownConnectorKindError

    if preset is not None and kind != "mcp":
        typer.echo("Error: --preset is only supported for MCP connectors.", err=True)
        raise typer.Exit(code=1)
    if kind == "mcp":
        connector_config = _mcp_connector_config(name=name, url=url, preset_id=preset, tools=tool)
    else:
        if not name:
            typer.echo("Error: --name is required.", err=True)
            raise typer.Exit(code=1)
        connector_config = ConnectorConfig(name=name, kind=kind, settings={})
    try:
        _registry(config).add(connector_config)
    except DuplicateConnectorError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    except UnknownConnectorKindError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Added {kind} connector '{connector_config.name}'.")
    env_vars = connector_config.settings.get("env_vars") or []
    if env_vars:
        typer.echo(f"Set {', '.join(str(item) for item in env_vars)} before health or ingest.")
    if connector_config.settings.get("auth") == "oauth":
        typer.echo("This server uses OAuth; the browser consent flow runs on first health/ingest.")


@connectors_app.command("health")
def health_connector(
    name: str = typer.Option(..., "--name", help="Connector name."),
    config: Path | None = ConfigOption,
) -> None:
    """Check whether a connector can reach its external system."""
    from connectors.registry import ConnectorNotFoundError, UnknownConnectorKindError

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
    config: Path | None = ConfigOption,
) -> None:
    """Ingest data from an external connector into the local ingest sink."""
    from connectors.registry import ConnectorNotFoundError, UnknownConnectorKindError

    try:
        connector_config = _registry(config).get(name)
        connector = build_connector(connector_config)
    except (ConnectorNotFoundError, UnknownConnectorKindError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    batch = asyncio.run(connector.ingest())
    get_default_sink().append(batch)
    typer.echo(batch.model_dump_json())
