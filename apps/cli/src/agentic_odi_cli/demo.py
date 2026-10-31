"""``odi demo`` — load a labelled sample workspace on purpose.

The demo is the only way a prospective user sees a filled canvas before they
have research of their own. It is deliberately additive: loading never clears
or overwrites the user's own rows, and every row it writes carries
``origin="demo"`` so the sample can never be mistaken for real data.
"""

from __future__ import annotations

import json

import typer

from agentic_odi_cli import context

demo_app = typer.Typer(help="Load a labelled sample workspace you can see without doing research.")


@demo_app.command("load")
def load(
    db: str | None = typer.Option(None, "--db", help="Path to the local store to fill."),
    name: str = typer.Option("demo", help="The demo workspace name."),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON."),
) -> None:
    """Fill a store with the labelled sample corpus; a second load is a no-op."""
    from agentic_odi_core.demo import load_demo
    from agentic_odi_core.sqlite_repository import SQLiteRepository

    repo = SQLiteRepository(db_path=db or context.config().db_path)
    try:
        result = load_demo(repo, name=name)
    finally:
        repo.commit()
        repo.close()

    payload = {
        "job_id": result.job_id,
        "jobs": result.jobs,
        "steps": result.steps,
        "outcomes": result.outcomes,
        "evidence": result.evidence,
        "origin": "demo",
    }
    if json_output:
        typer.echo(json.dumps(payload, indent=2))
    else:
        typer.echo(
            "Loaded the labelled demo workspace "
            f"({result.jobs} job, {result.steps} steps, "
            f"{result.outcomes} outcomes, {result.evidence} evidence rows)."
        )
        typer.echo(f'job_id: {result.job_id}   (every row carries origin="demo")')


@demo_app.command("clear")
def clear(
    db: str | None = typer.Option(None, "--db", help="Path to the local store to clear."),
    yes: bool = typer.Option(False, "--yes", help="Confirm removal without a prompt."),
) -> None:
    """Remove only the rows tagged ``origin="demo"``; user rows are untouched."""
    from agentic_odi_core.sqlite_repository import SQLiteRepository

    if not yes:
        typer.confirm('Remove every row tagged origin="demo"?', abort=True)

    repo = SQLiteRepository(db_path=db or context.config().db_path)
    removed = 0
    try:
        for outcome in list(repo.outcomes.values()):
            if outcome.origin == "demo":
                repo.delete_outcome(outcome.id)
                removed += 1
        for evidence in list(repo.evidence.values()):
            if evidence.origin == "demo":
                repo.delete_evidence(evidence.id)
                removed += 1
        for step in list(repo.steps.values()):
            if step.origin == "demo":
                repo.delete_step(step.id)
                removed += 1
        for job in list(repo.jobs.values()):
            if job.origin == "demo":
                repo.delete_job(job.id)
                removed += 1
    finally:
        repo.commit()
        repo.close()
    typer.echo(f"Removed {removed} demo rows. Your own rows were left untouched.")


__all__ = ["demo_app"]
