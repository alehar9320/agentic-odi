"""Desired Outcomes CLI subcommands.

ODI keeps two outcome shapes: the desired Outcome captured against a Job, and
the Customer Outcome that pairs customer value with business value. This module
owns the former; ``customer-outcomes`` owns the latter.
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import typer

from agentic_odi_cli import flags
from agentic_odi_cli.backend import run_tool
from agentic_odi_cli.render import (
    render_bulk_report,
    render_deleted,
    render_import_report,
    render_outcome,
    render_outcome_list,
    render_saved,
    render_search,
)

if TYPE_CHECKING:
    from agentic_odi_core import ClaimCheck, ImportRow, Step, Theme

desired_outcomes_app = typer.Typer(help="Manage desired Outcomes.")

JSON_OPTION = typer.Option(False, "--json", help="Emit machine-readable JSON.")
THEME_OPTION = typer.Option(None, "--theme", help="Theme ID; repeat for several themes")
TAG_OPTION = typer.Option(None, "--tag", help="Tag; repeat for several tags")
_ID_OPTION = typer.Option(None, "--id", help="Outcome ID; repeat for several outcomes")
_ADD_THEME_OPTION = typer.Option(None, "--add-theme", help="File under this theme; repeat")
_REMOVE_THEME_OPTION = typer.Option(None, "--remove-theme", help="Remove this theme; repeat")
_ADD_TAG_OPTION = typer.Option(None, "--add-tag", help="Add this tag; repeat")

EXPORT_FIELDS = (
    "id",
    "job_id",
    "step_id",
    "statement",
    "importance",
    "satisfaction",
    "opportunity_score",
)


@desired_outcomes_app.command("add")
def add(
    job_id: str = typer.Option(..., help="Job ID the outcome belongs to"),
    statement: str = typer.Option(..., help="Desired outcome statement"),
    importance: float = typer.Option(..., min=1.0, max=10.0, help="Importance score (1-10)"),
    satisfaction: float = typer.Option(..., min=1.0, max=10.0, help="Satisfaction score (1-10)"),
    step_id: str | None = typer.Option(default=None, help="Optional Step ID"),
    claim_check: str | None = typer.Option(
        None,
        "--claim-check",
        help="JSON claim check: the questions behind the score. Omit to record an unverified one.",
    ),
    json_output: bool = JSON_OPTION,
) -> None:
    """Add a desired Outcome to a Job.

    A score must carry the questions behind it. Pass ``--claim-check`` with the
    JSON you collected; without it the score is recorded as unverified, saying
    no customer questions were asked.
    """
    args: dict[str, Any] = {
        "job_id": job_id,
        "statement": statement,
        "importance": importance,
        "satisfaction": satisfaction,
    }
    if step_id is not None:
        args["step_id"] = step_id
    if claim_check is not None:
        try:
            args["claim_check"] = json.loads(claim_check)
        except json.JSONDecodeError as exc:
            raise typer.BadParameter(f"--claim-check must be valid JSON: {exc}") from exc
    else:
        from agentic_odi_core import manual_claim_check

        args["claim_check"] = manual_claim_check().model_dump(mode="json")
    typer.echo(
        render_saved("created", run_tool("add_outcome", args), as_json=json_output, noun="Outcome")
    )


@desired_outcomes_app.command("list")
def list_outcomes(
    job_id: str = typer.Option(..., help="Job ID to list outcomes for"),
    step_id: str | None = typer.Option(default=None, help="Filter by Step ID"),
    json_output: bool = JSON_OPTION,
) -> None:
    """List desired Outcomes for a Job."""
    args: dict[str, Any] = {"job_id": job_id}
    if step_id is not None:
        args["step_id"] = step_id
    typer.echo(render_outcome_list(run_tool("get_outcomes", args), as_json=json_output))


@desired_outcomes_app.command("export")
def export(
    job_id: str = typer.Option(..., help="Job ID to export outcomes for"),
    step_id: str | None = typer.Option(default=None, help="Filter by Step ID"),
    output_format: str = typer.Option("csv", "--format", help="Output format: csv or json."),
) -> None:
    """Export desired Outcomes to stdout, ready to pipe into another tool."""
    fmt = output_format.lower()
    if fmt not in {"csv", "json"}:
        typer.echo(f"Error: unknown format '{output_format}', expected csv or json", err=True)
        raise typer.Exit(code=1)
    args: dict[str, Any] = {"job_id": job_id}
    if step_id is not None:
        args["step_id"] = step_id
    outcomes = run_tool("get_outcomes", args)
    if not isinstance(outcomes, list):
        typer.echo(str(outcomes))
        return
    if fmt == "json":
        typer.echo(json.dumps(outcomes, indent=2))
        return
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=EXPORT_FIELDS, extrasaction="ignore")
    writer.writeheader()
    for item in outcomes:
        writer.writerow({field: item.get(field, "") for field in EXPORT_FIELDS})
    typer.echo(buffer.getvalue(), nl=False)


class ToolImportTarget:
    """The import loop's door to the tool layer.

    Every read and every write goes through ``run_tool``, so an imported row
    leaves exactly the way ``desired-outcomes add`` does: the same refusals, the
    same by-hand claim check behind a score, whether the backend is the local
    store or a running MCP server.
    """

    def themes(self, job_id: str) -> list[Theme]:
        from agentic_odi_core import Theme

        return [Theme.model_validate(item) for item in run_tool("list_themes", {"job_id": job_id})]

    def steps(self, job_id: str) -> list[Step]:
        from agentic_odi_core import Step

        return [Step.model_validate(item) for item in run_tool("get_job_map", {"job_id": job_id})]

    def existing_statements(self, job_id: str) -> list[str]:
        return [
            str(outcome.get("statement", ""))
            for outcome in run_tool("get_outcomes", {"job_id": job_id})
        ]

    def add_outcome(
        self,
        job_id: str,
        row: ImportRow,
        claim_check: ClaimCheck | None,
        step_id: str | None,
    ) -> str:
        args: dict[str, Any] = {"job_id": job_id, "statement": row.statement}
        if row.importance is not None:
            args["importance"] = row.importance
        if row.satisfaction is not None:
            args["satisfaction"] = row.satisfaction
        if step_id is not None:
            args["step_id"] = step_id
        if claim_check is not None:
            args["claim_check"] = claim_check.model_dump(mode="json")
        return str(run_tool("add_outcome", args)["id"])

    def assign_theme(self, outcome_ids: list[str], theme_id: str) -> None:
        run_tool("assign_theme", {"outcome_ids": outcome_ids, "theme_id": theme_id})


@desired_outcomes_app.command("import")
def import_file(
    path: str = typer.Argument(
        ..., help="CSV of outcome rows, as a research file or ``export`` writes one"
    ),
    job_id: str = typer.Option(..., help="Job ID the outcomes belong to"),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Report what this file would do without writing it"
    ),
    json_output: bool = JSON_OPTION,
) -> None:
    """Import a spreadsheet of desired Outcomes in one reviewable run.

    The rows go through the same door as ``desired-outcomes add``, so a row the
    CLI would refuse is refused here too: it is reported with its line number in
    the file and the rest still land. A row that carries scores is recorded as a
    by-hand score, because a spreadsheet is not an interview. ``--dry-run``
    writes nothing and reports what the real run would do. There is no undo token
    for an import — take a row back with ``desired-outcomes delete``.
    """
    run_tool("get_job", {"job_id": job_id})
    try:
        source = Path(path).read_bytes()
    except OSError as exc:
        typer.echo(f"Error: cannot read {path}: {exc.strerror or exc}", err=True)
        raise typer.Exit(code=1) from exc

    from agentic_odi_core import import_outcomes, parse_outcome_table

    report = import_outcomes(
        parse_outcome_table(source),
        ToolImportTarget(),
        job_id=job_id,
        dry_run=dry_run,
    )
    typer.echo(render_import_report(report, as_json=json_output))


@desired_outcomes_app.command("get")
def get(
    outcome_id: str = typer.Argument(..., help="Outcome ID"), json_output: bool = JSON_OPTION
) -> None:
    """Get a desired Outcome by ID."""
    typer.echo(
        render_outcome(run_tool("get_outcome", {"outcome_id": outcome_id}), as_json=json_output)
    )


@desired_outcomes_app.command("search")
def search(
    text: str | None = typer.Option(
        None,
        help="Case-insensitive substring of statements, theme names, and evidence",
    ),
    stage: str | None = typer.Option(None, help="Job-map stage, e.g. execute"),
    theme: list[str] | None = THEME_OPTION,
    confidence: str | None = typer.Option(None, help="scored or unscored"),
    tag: list[str] | None = TAG_OPTION,
    min_score: float | None = typer.Option(None, help="Lowest opportunity score (inclusive)"),
    max_score: float | None = typer.Option(None, help="Highest opportunity score (inclusive)"),
    job_id: str | None = typer.Option(None, help="Limit the search to one job"),
    sort: str = typer.Option("opportunity_score", help="opportunity_score or insertion"),
    limit: int | None = typer.Option(None, help="Page size"),
    offset: int = typer.Option(0, help="Skip this many results"),
    json_output: bool = JSON_OPTION,
) -> None:
    """Search the outcome library without leaving the terminal.

    One query, one answer everywhere: the CLI and ``GET /api/outcomes/search``
    run the same core search and get the same ids, total, and facet counts.
    """
    args: dict[str, Any] = {
        **_narrowing(
            text=text,
            stage=stage,
            theme=theme,
            confidence=confidence,
            tag=tag,
            min_score=min_score,
            max_score=max_score,
            job_id=job_id,
        ),
        "sort": sort,
        "limit": limit,
        "offset": offset,
    }
    result = run_tool("search_outcomes", args)
    theme_names = {} if json_output else _theme_names()
    typer.echo(render_search(result, as_json=json_output, theme_names=theme_names))


def _narrowing(
    *,
    text: str | None,
    stage: str | None,
    theme: list[str] | None,
    confidence: str | None,
    tag: list[str] | None,
    min_score: float | None,
    max_score: float | None,
    job_id: str | None,
) -> dict[str, Any]:
    """One spelling of the shared search options, reused by bulk so a filter means
    the same thing in both commands."""
    args: dict[str, Any] = {
        "text": text,
        "stage": stage,
        "confidence": confidence,
        "min_score": min_score,
        "max_score": max_score,
        "job_id": job_id,
    }
    if theme:
        args["theme_ids"] = theme
    if tag:
        args["tags"] = tag
    return args


def _theme_names() -> dict[str, str]:
    return {
        str(item.get("id", "")): str(item.get("name", "")) for item in run_tool("list_themes", {})
    }


@desired_outcomes_app.command("bulk")
def bulk(
    outcome_id: list[str] | None = _ID_OPTION,
    text: str | None = typer.Option(None, help="Narrow by substring, as ``search`` does"),
    stage: str | None = typer.Option(None, help="Narrow to outcomes filed on this stage"),
    theme: list[str] | None = THEME_OPTION,
    confidence: str | None = typer.Option(None, help="scored or unscored"),
    tag: list[str] | None = TAG_OPTION,
    min_score: float | None = typer.Option(None, help="Lowest opportunity score (inclusive)"),
    max_score: float | None = typer.Option(None, help="Highest opportunity score (inclusive)"),
    job_id: str | None = typer.Option(None, help="Narrow the set to one job"),
    set_stage: str | None = typer.Option(
        None, "--set-stage", help="Move every selected outcome onto this job-map stage"
    ),
    add_theme: list[str] | None = _ADD_THEME_OPTION,
    remove_theme: list[str] | None = _REMOVE_THEME_OPTION,
    add_tag: list[str] | None = _ADD_TAG_OPTION,
    dry_run: bool = typer.Option(False, "--dry-run", help="Report the rows without writing them"),
    json_output: bool = JSON_OPTION,
) -> None:
    """Organise a set of outcomes in one reviewable run.

    The selected rows are the ``--id`` flags unioned with every match of the
    narrowing, which is the same search ``odi desired-outcomes search`` runs and
    is read without a page limit: "everything in this theme" means everything.
    Each row answers for itself, so one outcome filed under another job's theme
    is reported as a skip and the rest still land. ``--dry-run`` writes nothing
    and hands back no token.
    """
    narrowing = _narrowing(
        text=text,
        stage=stage,
        theme=theme,
        confidence=confidence,
        tag=tag,
        min_score=min_score,
        max_score=max_score,
        job_id=job_id,
    )
    ids = list(dict.fromkeys(outcome_id or []))
    if any(narrowing.values()):
        matched = run_tool("search_outcomes", narrowing)
        ids += [str(item["id"]) for item in matched.get("items", []) if item.get("id") not in ids]

    args: dict[str, Any] = {"outcome_ids": ids, "dry_run": dry_run}
    if add_theme:
        args["add_theme_ids"] = add_theme
    if remove_theme:
        args["remove_theme_ids"] = remove_theme
    if set_stage:
        args["stage"] = set_stage
    if add_tag:
        args["add_tags"] = add_tag
    report = run_tool("bulk_update_outcomes", args)
    theme_names = {} if json_output else _theme_names()
    typer.echo(
        render_bulk_report(
            report,
            as_json=json_output,
            theme_names=theme_names,
            mode="preview" if dry_run else "apply",
        )
    )


@desired_outcomes_app.command("undo")
def undo(
    token: str = typer.Argument(..., help="The undo token a bulk run printed"),
    json_output: bool = JSON_OPTION,
) -> None:
    """Take a bulk run back.

    The token is single-use and single-active: a newer bulk run retires it, and a
    row edited since then is left alone and reported rather than overwritten.
    """
    report = run_tool("undo_bulk", {"token": token})
    theme_names = {} if json_output else _theme_names()
    typer.echo(
        render_bulk_report(report, as_json=json_output, theme_names=theme_names, mode="undo")
    )


@desired_outcomes_app.command("update")
def update(
    outcome_id: str = typer.Argument(..., help="Outcome ID"),
    statement: str | None = typer.Option(default=None, help="New statement"),
    importance: float | None = typer.Option(default=None, min=1.0, max=10.0),
    satisfaction: float | None = typer.Option(default=None, min=1.0, max=10.0),
    step_id: str | None = typer.Option(default=None, help="Move to a Step"),
    json_output: bool = JSON_OPTION,
) -> None:
    """Update a desired Outcome."""
    args: dict[str, Any] = {"outcome_id": outcome_id}
    if statement is not None:
        args["statement"] = statement
    if importance is not None:
        args["importance"] = importance
    if satisfaction is not None:
        args["satisfaction"] = satisfaction
    if step_id is not None:
        args["step_id"] = step_id
    typer.echo(
        render_saved(
            "updated", run_tool("update_outcome", args), as_json=json_output, noun="Outcome"
        )
    )


@desired_outcomes_app.command("evaluate")
def evaluate(
    statement: str = typer.Argument(..., help="Outcome statement to check"),
    job_id: str | None = typer.Option(default=None, help="Job to compare against"),
    json_output: bool = JSON_OPTION,
) -> None:
    """Evaluate an outcome statement against ODI format rules."""
    args: dict[str, Any] = {"statement": statement}
    if job_id is not None:
        args["job_id"] = job_id
    result = run_tool("evaluate_outcome", args)
    if json_output:
        typer.echo(result if isinstance(result, str) else json.dumps(result))
        return
    parsed = json.loads(result) if isinstance(result, str) else result
    verdict = "passes" if parsed.get("valid") else "needs work"
    typer.echo(f"{verdict}: {statement}")
    for problem in parsed.get("issues", []):
        typer.echo(f"  - {problem}")
    if flags.is_enabled("advanced_metrics"):
        for suggestion in parsed.get("suggestions", []):
            typer.echo(f"  Suggestion: {suggestion}")


@desired_outcomes_app.command("delete")
def delete(
    outcome_id: str = typer.Argument(..., help="Outcome ID"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
    json_output: bool = JSON_OPTION,
) -> None:
    """Delete a desired Outcome."""
    if not yes:
        confirm = typer.confirm(f"Delete outcome {outcome_id}?")
        if not confirm:
            raise typer.Exit()
    typer.echo(
        render_deleted(
            run_tool("delete_outcome", {"outcome_id": outcome_id}),
            as_json=json_output,
            noun="outcome",
        )
    )
