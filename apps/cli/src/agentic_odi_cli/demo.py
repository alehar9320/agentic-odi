"""A demo workspace you can load on purpose.

``odi demo load`` fills a store with one complete ODI study, so a first run has
something to look at before there is any research of your own. The rows arrive
labeled ``origin="demo"`` and re-running the command changes nothing, which is
what makes it safe to try. M0-13.2 adds the visible chip and ``odi demo clear``;
this command only ever adds.
"""

from __future__ import annotations

from dataclasses import asdict

import typer

from agentic_odi_cli.backend import run_local
from agentic_odi_cli.render import render_demo_load

demo_app = typer.Typer(help="Load the study that ships with the product.")

JSON_OPTION = typer.Option(False, "--json", help="Emit machine-readable JSON.")


@demo_app.command("load")
def load(
    job_id: str = typer.Option(
        None,
        "--job",
        help="Attach the study to a job you already have instead of its own",
    ),
    json_output: bool = JSON_OPTION,
) -> None:
    """Load one complete ODI study, labeled as a demo and safe to re-run."""
    #: Imported on the way in, so `--help` does not load the domain layer.
    from agentic_odi_core.demo import load_demo_workspace

    result = run_local(lambda service: load_demo_workspace(service, job_id=job_id))
    typer.echo(render_demo_load(asdict(result), as_json=json_output))
