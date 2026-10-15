"""External data connector CLI subcommands."""

from __future__ import annotations

import asyncio
from typing import Annotated

import typer
from connectors import (
    ConnectorConfig,
    ConnectorNotFoundError,
    ConnectorRegistry,
    DuplicateConnectorError,
    IngestSink,
    build_connector,
)

connectors_app = typer.Typer(help="Manage external data connectors.")
add_app = typer.Typer(help="Add a connector.")
connectors_app.add_typer(add_app, name="add")

ConfigOption = Annotated[
    str | None, typer.Option("--config", help="Path to the connectors config file")
]


def _registry(config_path: str | None) -> ConnectorRegistry:
    if config_path is None:
        return ConnectorRegistry()
    return ConnectorRegistry(config_path)


def _sink() -> IngestSink:
    return IngestSink()


def _get_config(name: str, config_path: str | None) -> ConnectorConfig:
    try:
        return _registry(config_path).get(name)
    except ConnectorNotFoundError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc


@connectors_app.command("list")
def list_connectors(config: ConfigOption = None) -> None:
    """List configured connectors."""
    configs = _registry(config).list()
    if not configs:
        typer.echo("No connectors configured.")
        return
    for connector in configs:
        typer.echo(f"{connector.name}\t{connector.kind}\t{connector.enabled}")


@add_app.command("mcp")
def add_mcp(
    name: Annotated[str, typer.Option("--name", help="Connector name")],
    url: Annotated[str, typer.Option("--url", help="MCP server URL")],
    tool: Annotated[list[str] | None, typer.Option("--tool", help="Tool name to ingest")] = None,
    config: ConfigOption = None,
) -> None:
    """Add an MCP connector."""
    connector_config = ConnectorConfig(
        name=name,
        kind="mcp",
        settings={"url": url, "tools": tool or []},
    )
    try:
        _registry(config).add(connector_config)
    except DuplicateConnectorError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Added connector {name!r}.")


@connectors_app.command("health")
def health(
    name: Annotated[str, typer.Option("--name", help="Connector name")],
    config: ConfigOption = None,
) -> None:
    """Check that a connector is reachable."""
    connector_config = _get_config(name, config)
    status = asyncio.run(build_connector(connector_config, _sink()).health())
    typer.echo(f"{'ok' if status.ok else 'not ok'}: {status.detail}")
    if not status.ok:
        raise typer.Exit(code=1)


@connectors_app.command("ingest")
def ingest(
    name: Annotated[str, typer.Option("--name", help="Connector name")],
    dump: Annotated[
        str | None, typer.Option("--dump", help="Path to dump ingested records as JSON")
    ] = None,
    config: ConfigOption = None,
) -> None:
    """Ingest data from a connector."""
    connector_config = _get_config(name, config)
    sink = _sink()
    batch = asyncio.run(build_connector(connector_config, sink).ingest())
    typer.echo(
        f"{batch.connector_name}: {len(batch.records)} record(s), {len(batch.errors)} error(s)"
    )
    if dump is not None:
        sink.dump(dump)
