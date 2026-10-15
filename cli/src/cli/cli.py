"""Main CLI entry point."""

import typer

from cli import context, version
from cli.connectors import connectors_app
from cli.outcomes import outcomes_app
from cli.version import __version__  # noqa: F401  (re-exported for tests)

app = typer.Typer(
    name="agentic-odi-cli",
    help="Agentic ODI CLI - Tool for managing Jobs-to-be-Done (JTBD) and ODI workflows.",
)
app.add_typer(connectors_app, name="connectors")

app.add_typer(outcomes_app, name="outcomes", help="Manage Customer Outcomes")


def _version_callback(ctx: typer.Context, value: bool) -> None:
    if value:
        if ctx.params.get("verbose"):
            typer.echo(version.verbose_summary())
        else:
            typer.echo(version.build_summary())
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False, "--version", callback=_version_callback, help="Show version"
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        is_eager=True,
        help="Show verbose version information (with --version)",
    ),
    backend: str | None = typer.Option(None, "--backend", help="Backend: local | mcp"),
) -> None:  # noqa: B008
    context.set_backend(backend)


@app.command(name="version")
def version_cmd() -> None:
    """Show CLI version."""
    typer.echo(version.build_summary())


if __name__ == "__main__":
    app()
