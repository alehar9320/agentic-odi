"""Survey import CLI subcommands (B2).

``odi survey import <csv>`` reads a well-formed responses file and lands each
outcome's accepted mean, sample size and band on the matching outcome.

``--dry-run`` prints the same match report the real run would produce and writes
nothing. ``--match`` suggests a single candidate for an unmatched or ambiguous
reference, which a person confirms: a suggestion is never applied silently
(B2.2). Every source row is named by its 1-based CSV line, so no row disappears
without a report line.
"""

from __future__ import annotations

import csv
import json
from typing import Any

import typer

from agentic_odi_cli.backend import run_tool

survey_app = typer.Typer(help="Import survey responses as measured scores.")

JSON_OPTION = typer.Option(False, "--json", help="Emit machine-readable JSON.")


def _read_rows(path: str) -> list[dict[str, Any]]:
    """Read a responses CSV, tagging each row with its 1-based physical line.

    A quoted field may span several physical lines, so the record's *starting*
    line is recorded under ``_line``; the header is line 1. ``plan_survey``
    prefers ``_line`` when present, so a rejected row names the line a person
    sees in their editor rather than the record's ordinal position.
    """
    try:
        with open(path, newline="", encoding="utf-8") as handle:
            reader = csv.reader(handle)
            try:
                header = next(reader)
            except StopIteration:
                return []
            rows: list[dict[str, Any]] = []
            previous = 1  # the header is physical line 1
            for record in reader:
                start = previous + 1
                previous = reader.line_num
                row: dict[str, Any] = dict(zip(header, record, strict=False))
                row["_line"] = start
                rows.append(row)
            return rows
    except OSError as err:
        raise typer.BadParameter(f"cannot read {path}: {err}") from err


def _render_plan(plan: dict[str, Any], *, dry_run: bool) -> None:
    verb = "Would import" if dry_run else "Imported"
    counts = plan["counts"]
    typer.echo(
        f"{verb} {counts['accepted']} of {counts['total']} row(s); "
        f"{counts['unmatched']} unmatched, {counts['ambiguous']} ambiguous, "
        f"{counts['invalid']} invalid."
    )
    for row in plan["rows"]:
        if row["status"] == "accepted":
            continue
        hint = f" (suggested match: {row['suggestion']})" if row.get("suggestion") else ""
        typer.echo(f"  line {row['line']} [{row['status']}] {row['reason']}{hint}")


def _confirm_suggestions(plan: dict[str, Any]) -> dict[str, str]:
    """Ask the person to accept each suggested match, one per reference (B2.2).

    A suggestion is never applied silently: only a ``yes`` becomes a confirmed
    assignment. The same reference is asked once, however many rows carry it.
    """
    confirmed: dict[str, str] = {}
    asked: set[str] = set()
    for row in plan["rows"]:
        if row["status"] == "accepted" or not row.get("suggestion"):
            continue
        ref = row["outcome_ref"]
        if ref in asked:
            continue
        asked.add(ref)
        prompt = f"Line {row['line']}: match {ref!r} to {row['suggestion']!r}?"
        if typer.confirm(prompt, default=False):
            confirmed[ref] = row["suggestion"]
    return confirmed


@survey_app.command("import")
def import_survey(
    path: str = typer.Argument(..., help="Path to a CSV of survey responses"),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Print the match report and write nothing."
    ),
    match: bool = typer.Option(
        False,
        "--match",
        help="Propose a candidate for each unmatched reference and confirm before writing.",
    ),
    json_output: bool = JSON_OPTION,
) -> None:
    """Land a survey's per-outcome means, sample and band on matching outcomes."""
    rows = _read_rows(path)
    if not rows:
        typer.echo("Error: survey file has no rows", err=True)
        raise typer.Exit(code=1)

    if dry_run:
        plan = run_tool("get_survey_import_plan", {"rows": rows})
        if json_output:
            typer.echo(json.dumps(plan, indent=2, sort_keys=True))
            return
        _render_plan(plan, dry_run=True)
        return

    confirmed: dict[str, str] = {}
    if match:
        plan = run_tool("get_survey_import_plan", {"rows": rows})
        unresolved = plan["counts"]["unmatched"] + plan["counts"]["ambiguous"]
        if unresolved:
            _render_plan(plan, dry_run=True)
            confirmed = _confirm_suggestions(plan)
            if not confirmed:
                typer.echo("No matches confirmed; nothing was written.")
                raise typer.Exit(code=1)

    updated = run_tool("commit_survey_import", {"rows": rows, "confirmed_matches": confirmed})
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
