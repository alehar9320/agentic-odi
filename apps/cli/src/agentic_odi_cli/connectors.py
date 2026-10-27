"""CLI adapter for listing, adding, checking, and ingesting external connectors."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import TYPE_CHECKING

import typer

from agentic_odi_cli.backend import run_tool
from agentic_odi_cli.render import render_saved

# The connectors package eagerly imports fastmcp via ``connectors/__init__``.
# Import it lazily so that merely loading the CLI (e.g. ``odi --version``) does
# not pay the fastmcp/mcp import cost. The wrappers below keep stable module
# attributes for tests to monkeypatch.
if TYPE_CHECKING:
    from agentic_odi_connectors.mapping import EvidenceDraft
    from agentic_odi_connectors.models import ConnectorConfig
    from agentic_odi_connectors.protocol import Connector
    from agentic_odi_connectors.registry import ConnectorRegistry
    from agentic_odi_connectors.sink import IngestSink

connectors_app = typer.Typer(
    name="connectors",
    help="Connect Agentic ODI to external systems.",
    no_args_is_help=True,
)


def build_connector(config: ConnectorConfig) -> Connector:
    from agentic_odi_connectors.factory import build_connector as _build_connector

    return _build_connector(config)


def get_default_sink() -> IngestSink:
    from agentic_odi_connectors.sink import get_default_sink as _get_default_sink

    return _get_default_sink()


def drafts_from_batch(
    batch,
    *,
    job_id: str | None = None,
    step_id: str | None = None,
    outcome_id: str | None = None,
) -> list[EvidenceDraft]:
    from agentic_odi_connectors.mapping import drafts_from_batch as _drafts_from_batch

    return _drafts_from_batch(batch, job_id=job_id, step_id=step_id, outcome_id=outcome_id)


def _config_path(config: Path | None) -> Path:
    if config is not None:
        return config
    env = os.getenv("AGENTIC_ODI_CONNECTORS_FILE")
    if env:
        return Path(env)
    return Path.cwd() / ".agentic-odi" / "connectors.json"


def _registry(config: Path | None) -> ConnectorRegistry:
    from agentic_odi_connectors.registry import ConnectorRegistry

    return ConnectorRegistry(_config_path(config))


def _parse_headers(values: list[str] | None) -> dict[str, str]:
    headers: dict[str, str] = {}
    for raw in values or []:
        key, separator, value = raw.partition("=")
        if not separator or not key.strip():
            typer.echo(f"Error: invalid header '{raw}', expected KEY=VALUE", err=True)
            raise typer.Exit(code=1)
        headers[key.strip()] = value.strip()
    return headers


ConfigOption = typer.Option(
    None,
    "--config",
    help="Path to the connectors JSON registry.",
    envvar="AGENTIC_ODI_CONNECTORS_FILE",
)

_CONNECTOR_TIMEOUT = 30.0


def _connector_timeout() -> float:
    raw = os.getenv("AGENTIC_ODI_CONNECTOR_TIMEOUT")
    if not raw:
        return _CONNECTOR_TIMEOUT
    try:
        return float(raw)
    except ValueError:
        return _CONNECTOR_TIMEOUT


def _run(coro, name: str):
    """Run a connector coroutine with a bounded timeout and clean failure."""
    timeout = _connector_timeout()
    try:
        return asyncio.run(asyncio.wait_for(coro, timeout=timeout))
    except asyncio.TimeoutError as exc:
        typer.echo(f"Error: connector '{name}' timed out after {timeout:.0f}s", err=True)
        raise typer.Exit(code=1) from exc


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
    from agentic_odi_connectors.catalog import AREA_LABELS, UnknownAreaError, list_presets

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
    from agentic_odi_connectors.catalog import (
        UnknownPresetError,
        connector_config_from_preset,
        get_preset,
    )
    from agentic_odi_connectors.models import ConnectorConfig

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
    kind: str = typer.Argument(..., help="Connector kind (mcp, rest, or webhook)."),
    name: str | None = typer.Option(
        None, "--name", help="Unique connector name (defaults to the preset id)."
    ),
    url: str | None = typer.Option(
        None, "--url", help="Endpoint URL (required unless --preset is given)."
    ),
    preset: str | None = typer.Option(
        None, "--preset", help="Preset id from 'connectors catalog'."
    ),
    tool: list[str] | None = typer.Option(  # noqa: B008
        None,
        "--tool",
        help="MCP tool to call during ingest. Repeatable.",
    ),
    method: str | None = typer.Option(None, "--method", help="HTTP method for REST/webhook."),
    header: list[str] | None = typer.Option(  # noqa: B008
        None, "--header", help="HTTP header as KEY=VALUE. Repeatable."
    ),
    records_key: str | None = typer.Option(
        None, "--records-key", help="Dot path to the record list in the response."
    ),
    config: Path | None = ConfigOption,
) -> None:
    """Register a new external connector, optionally from a known preset."""
    from agentic_odi_connectors.models import ConnectorConfig
    from agentic_odi_connectors.registry import DuplicateConnectorError, UnknownConnectorKindError

    if preset is not None and kind != "mcp":
        typer.echo("Error: --preset is only supported for MCP connectors.", err=True)
        raise typer.Exit(code=1)
    if kind == "mcp":
        connector_config = _mcp_connector_config(name=name, url=url, preset_id=preset, tools=tool)
    elif kind in {"rest", "webhook"}:
        if not name:
            typer.echo("Error: --name is required.", err=True)
            raise typer.Exit(code=1)
        if not url:
            typer.echo(f"Error: --url is required for {kind.upper()} connectors.", err=True)
            raise typer.Exit(code=1)
        settings: dict[str, object] = {"url": url}
        if method:
            settings["method"] = method.upper()
        headers = _parse_headers(header)
        if headers:
            settings["headers"] = headers
        if records_key:
            settings["records_key"] = records_key
        connector_config = ConnectorConfig(name=name, kind=kind, settings=settings)
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
    from agentic_odi_connectors.registry import ConnectorNotFoundError, UnknownConnectorKindError

    try:
        connector_config = _registry(config).get(name)
        connector = build_connector(connector_config)
    except (ConnectorNotFoundError, UnknownConnectorKindError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    status = _run(connector.health(), name)
    typer.echo(status.model_dump_json())
    if not status.ok:
        raise typer.Exit(code=1)


@connectors_app.command("ingest")
def ingest_connector(
    name: str = typer.Option(..., "--name", help="Connector name."),
    job_id: str | None = typer.Option(None, "--job-id", help="Link evidence to a Job."),
    step_id: str | None = typer.Option(None, "--step-id", help="Link evidence to a Step."),
    outcome_id: str | None = typer.Option(
        None, "--outcome-id", help="Link evidence to a desired Outcome."
    ),
    config: Path | None = ConfigOption,
) -> None:
    """Ingest connector records and optionally map them into ODI evidence."""
    from agentic_odi_connectors.registry import ConnectorNotFoundError, UnknownConnectorKindError

    try:
        connector_config = _registry(config).get(name)
        connector = build_connector(connector_config)
    except (ConnectorNotFoundError, UnknownConnectorKindError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    batch = _run(connector.ingest(), name)
    get_default_sink().append(batch)
    typer.echo(batch.model_dump_json())
    if job_id is None and step_id is None and outcome_id is None:
        return
    drafts = drafts_from_batch(batch, job_id=job_id, step_id=step_id, outcome_id=outcome_id)
    for draft in drafts:
        typer.echo(
            render_saved(
                "created",
                run_tool(
                    "add_evidence",
                    {
                        "source_name": draft.source_name,
                        "source_kind": draft.source_kind,
                        "item_type": draft.item_type,
                        "name": draft.name,
                        "content": draft.content,
                        "url": draft.url,
                        "raw": draft.raw,
                        "job_id": draft.job_id,
                        "step_id": draft.step_id,
                        "outcome_id": draft.outcome_id,
                    },
                ),
                as_json=False,
                noun="Evidence",
            )
        )
