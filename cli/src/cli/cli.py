"""Agentic ODI command-line interface."""

import typer

from cli.outcomes import outcomes_app

__version__ = "0.1.0"

app = typer.Typer(
    name="agentic-odi",
    help="Agentic ODI command-line interface.",
    no_args_is_help=True,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"agentic-odi {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        None,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show the version and exit.",
    ),
) -> None:
    """Agentic ODI command-line interface."""


app.add_typer(outcomes_app, name="outcomes", help="Manage Customer Outcome entities.")
