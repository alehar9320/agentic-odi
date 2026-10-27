"""Capabilities CLI commands."""

from __future__ import annotations

import json

import typer

from agentic_odi_cli.backend import run_tool

capabilities_app = typer.Typer(
    name="capabilities",
    help="Explore available agentic ODI capabilities and tool manifests.",
)


@capabilities_app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    as_json: bool = typer.Option(False, "--json", help="Format manifest as JSON"),
) -> None:
    if ctx.invoked_subcommand is None:
        if as_json:
            manifest = run_tool("get_capabilities_manifest", {})
            typer.echo(json.dumps(manifest, indent=2))
        else:
            summary = run_tool("get_capabilities", {})
            typer.echo(summary)


@capabilities_app.command(name="tools")
def tools_cmd(
    as_json: bool = typer.Option(False, "--json", help="Output tool names as JSON array"),
) -> None:
    """List tool names exposed by the system contract."""
    manifest = run_tool("get_capabilities_manifest", {})
    tool_names = sorted(manifest.get("tools", {}).keys())
    if as_json:
        typer.echo(json.dumps(tool_names, indent=2))
    else:
        for name in tool_names:
            typer.echo(name)
