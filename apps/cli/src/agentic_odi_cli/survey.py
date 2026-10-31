"""Survey import CLI subcommands (B2).

``odi survey import <csv>`` reads a well-formed responses file and lands each
outcome's accepted mean, sample size and band on the matching outcome. Dry-run,
line reporting and human-confirmed matching are B2.2 and are not here: this
imports a well-formed file correctly or fails without a partial write.
"""

from __future__ import annotations

import csv
import json
from typing import Any

import typer

from agentic_odi_cli.backend import run_tool

survey_app = typer.Typer(help="Import survey responses as measured scores.")

JSON_OPTION = typer.Option(False, "--json", help="Emit machine-readable JSON.")


@survey_app.command("import")
def import_survey(
    path: str = typer.Argument(..., help="Path to a CSV of survey responses"),
    json_output: bool = JSON_OPTION,
) -> None:
    """Land a survey's per-outcome means, sample and band on matching outcomes."""
    with open(path, newline="", encoding="utf-8") as handle:
        rows: list[dict[str, Any]] = list(csv.DictReader(handle))
    updated = run_tool("import_survey", {"rows": rows})
    if json_output:
        typer.echo(json.dumps(updated, indent=2, sort_keys=True))
        return
    if not updated:
        typer.echo("No outcomes matched; nothing was written.")
        return
    typer.echo(f"Imported a survey for {len(updated)} outcome(s):")
    for outcome_id, outcome in sorted(updated.items()):
        typer.echo(
            f"  {outcome_id}: importance={outcome['importance']} "
            f"satisfaction={outcome['satisfaction']} n={outcome['importance_n']} "
            f"method={outcome['score_method']} "
            f"band=[{outcome.get('opportunity_low')}, {outcome.get('opportunity_high')}]"
        )
