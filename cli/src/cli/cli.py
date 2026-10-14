"""Main CLI entry point."""

import typer

from cli.outcomes import outcomes_app
from cli.version import __version__

app = typer.Typer(
    name="agentic-odi-cli",
    help="Agentic ODI CLI - Tool for managing Jobs-to-be-Done (JTBD) and ODI workflows.",
)

app.add_typer(outcomes_app, name="outcomes", help="Manage Customer Outcomes")


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False, "--version", callback=_version_callback, help="Show version"
    ),
) -> None:  # noqa: B008
    pass


@app.command()
def version_cmd() -> None:
    """Show CLI version."""
    typer.echo(__version__)


if __name__ == "__main__":
    app()
