"""`odi data` command group: inspect the local data files.

The group exists so a person can find the exact files the *current*
configuration uses, without guessing platform-specific defaults or reading
environment configuration by hand. It never opens a database, prints
credentials, or exports data — it only reports resolved paths.
"""

from __future__ import annotations

import json

import typer

data_app = typer.Typer(
    name="data",
    help="Inspect the local ODI data files.",
)


@data_app.command(name="path")
def path_cmd(
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON."),
) -> None:
    """Print the resolved paths for the ODI and Studio databases.

    Each path is the one the current configuration uses, honoring
    ``AGENTIC_ODI_DB`` and ``AGENTIC_ODI_STUDIO_DB`` overrides. The files are
    not opened and the directories are not created — a missing parent shows up
    as a resolved path, nothing more.
    """
    # Imported lazily so ``agentic-odi --version`` and ``--help`` stay
    # lightweight: the CLI entrypoint must not pull in the core package at
    # module load time (see test_startup_perf.py).
    from agentic_odi_core.paths import default_odi_db_path, default_studio_db_path

    odi = default_odi_db_path()
    studio = default_studio_db_path()

    if json_output:
        typer.echo(
            json.dumps(
                {
                    "odi_db": str(odi),
                    "studio_db": str(studio),
                    "odi_env": "AGENTIC_ODI_DB",
                    "studio_env": "AGENTIC_ODI_STUDIO_DB",
                },
                indent=2,
            )
        )
        return

    typer.echo(f"ODI database:   {odi}")
    typer.echo(f"Studio memory:  {studio}")


@data_app.callback(invoke_without_command=True)
def data_cmd(
    ctx: typer.Context,
) -> None:
    """Inspect the local ODI data files."""
    if ctx.invoked_subcommand is not None:
        return
    typer.echo(ctx.get_help())
