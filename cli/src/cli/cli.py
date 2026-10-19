"""Main CLI entry point."""

from __future__ import annotations

import typer

from cli import version as version_info
from cli.backend import BackendConfig
from cli.connectors import connectors_app
from cli.customer_outcomes import customer_outcomes_app, score

app = typer.Typer(
    name="agentic-odi-cli",
    help="Agentic ODI CLI - Tool for managing Jobs-to-be-Done (JTBD) and ODI workflows.",
)
app.add_typer(connectors_app, name="connectors")
app.add_typer(customer_outcomes_app, name="customer-outcomes", help="Manage Customer Outcomes.")
app.add_typer(
    customer_outcomes_app,
    name="outcomes",
    help="Alias for customer-outcomes.",
    hidden=True,
)
app.command(name="score")(score)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(version_info.__version__)
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(
        False, "--version", callback=_version_callback, help="Show version and exit."
    ),
    backend: str | None = typer.Option(
        None, "--backend", help="Backend to use: local (SQLite) | mcp (remote server)."
    ),
    db: str | None = typer.Option(
        None, "--db", help="Path to the local SQLite database (local backend)."
    ),
    mcp_url: str | None = typer.Option(None, "--mcp-url", help="MCP server URL (mcp backend)."),
) -> None:
    """Agentic ODI: manage Customer Outcomes locally or against an MCP server."""
    ctx.obj = BackendConfig(backend=backend, db_path=db, mcp_url=mcp_url)
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit()


@app.command(name="version")
def version_cmd() -> None:
    """Show CLI version."""
    typer.echo(version_info.__version__)


if __name__ == "__main__":
    app()
