"""Evidence CLI subcommands.

Evidence is captured research that supports a Job, Step, or desired Outcome.
Records usually arrive from connectors, but they can also be entered by hand and
later promoted into ODI artifacts.
"""

from __future__ import annotations

import sys
from enum import Enum
from pathlib import Path
from typing import Any, NoReturn

import typer

from agentic_odi_cli.backend import run_tool
from agentic_odi_cli.render import (
    render_deleted,
    render_evidence,
    render_evidence_list,
    render_saved,
)

evidence_app = typer.Typer(help="Manage evidence captured from connectors.")

JSON_OPTION = typer.Option(False, "--json", help="Emit machine-readable JSON.")

# The Studio caps how much of a text file the model sees; the CLI honours the
# same number so a pasted quote and an attached file are the same size of record.
MAX_EVIDENCE_FILE_CHARS = 20_000

TEXT_SUFFIXES = (".txt", ".md", ".markdown", ".vtt", ".srt")

# Parsers the CLI does not carry: no PDF or DOCX dependency exists in the
# workspace, so refusing is honest where pretending to read would produce junk.
UNREADABLE_SUFFIXES = (".pdf", ".docx")

STUDIO_HINT = "not supported from the CLI yet — attach it in the Studio (issue #380)"


class PromoteTarget(str, Enum):
    JOB = "job"
    OUTCOME = "outcome"


def _fail(message: str) -> NoReturn:
    typer.secho(f"Error: {message}", fg="red", err=True)
    raise typer.Exit(1)


def _read_file_text(file: str) -> str:
    """The text behind ``--file``, or a user-facing refusal. Never a traceback."""
    if file == "-":
        return sys.stdin.read()

    path = Path(file)
    suffix = path.suffix.lower()
    if suffix in UNREADABLE_SUFFIXES:
        _fail(f"{path.name} is {STUDIO_HINT}")
    if suffix not in TEXT_SUFFIXES:
        _fail(f"{path.name} is not a text format the CLI reads ({', '.join(TEXT_SUFFIXES)}).")
    if not path.is_file():
        _fail(f"No such file: {file}")

    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        _fail(f"Could not read {file}: {exc.strerror or exc}")


def _evidence_content(content: str | None, file: str | None) -> str:
    """Inline text or file text, capped the same way the Studio caps an attachment."""
    if (content is None) == (file is None):
        _fail("Provide exactly one of --content or --file.")
    if content is not None:
        return content
    text = _read_file_text(str(file))
    if not text.strip():
        _fail("That file contains no text.")
    if len(text) > MAX_EVIDENCE_FILE_CHARS:
        typer.secho(
            f"Kept {MAX_EVIDENCE_FILE_CHARS} of {len(text)} characters.",
            fg="yellow",
            err=True,
        )
    return text[:MAX_EVIDENCE_FILE_CHARS]


@evidence_app.command("add")
def add(
    source_name: str = typer.Option(..., help="Where the record came from"),
    name: str = typer.Option(..., help="Short label for the record"),
    content: str | None = typer.Option(
        default=None, help="Normalized text content (provide this or --file)"
    ),
    file: str | None = typer.Option(
        default=None,
        help="Read the content from a .txt, .md, .markdown, .vtt, or .srt file, or - for stdin",
    ),
    url: str | None = typer.Option(default=None, help="External link to evidence in source system"),
    source_kind: str = typer.Option("manual", help="Connector kind or 'manual'"),
    item_type: str = typer.Option(
        "manual", help="catalog | resource | tool_result | manual | note"
    ),
    job_id: str | None = typer.Option(default=None),
    step_id: str | None = typer.Option(default=None),
    outcome_id: str | None = typer.Option(default=None),
    json_output: bool = JSON_OPTION,
) -> None:
    """Add a research record as evidence."""
    args: dict[str, Any] = {
        "source_name": source_name,
        "source_kind": source_kind,
        "item_type": item_type,
        "name": name,
        "content": _evidence_content(content, file),
    }
    if url is not None:
        args["url"] = url
    if job_id is not None:
        args["job_id"] = job_id
    if step_id is not None:
        args["step_id"] = step_id
    if outcome_id is not None:
        args["outcome_id"] = outcome_id
    typer.echo(
        render_saved(
            "created", run_tool("add_evidence", args), as_json=json_output, noun="Evidence"
        )
    )


@evidence_app.command("list")
def list_evidence(
    job_id: str | None = typer.Option(default=None, help="Filter by Job ID"),
    step_id: str | None = typer.Option(default=None, help="Filter by Step ID"),
    outcome_id: str | None = typer.Option(default=None, help="Filter by Outcome ID"),
    json_output: bool = JSON_OPTION,
) -> None:
    """List captured evidence."""
    args: dict[str, Any] = {}
    if job_id is not None:
        args["job_id"] = job_id
    if step_id is not None:
        args["step_id"] = step_id
    if outcome_id is not None:
        args["outcome_id"] = outcome_id
    typer.echo(render_evidence_list(run_tool("list_evidence", args), as_json=json_output))


@evidence_app.command("get")
def get(
    evidence_id: str = typer.Argument(..., help="Evidence ID"), json_output: bool = JSON_OPTION
) -> None:
    """Get one evidence record by ID."""
    typer.echo(
        render_evidence(run_tool("get_evidence", {"evidence_id": evidence_id}), as_json=json_output)
    )


@evidence_app.command("delete")
def delete(
    evidence_id: str = typer.Argument(..., help="Evidence ID"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
    json_output: bool = JSON_OPTION,
) -> None:
    """Delete an evidence record."""
    if not yes:
        confirm = typer.confirm(f"Delete evidence {evidence_id}?")
        if not confirm:
            raise typer.Exit()
    typer.echo(
        render_deleted(
            run_tool("delete_evidence", {"evidence_id": evidence_id}),
            as_json=json_output,
            noun="evidence",
        )
    )


@evidence_app.command("promote")
def promote(
    evidence_id: str = typer.Argument(..., help="Evidence ID"),
    to: PromoteTarget = typer.Option(..., "--to", help="Create a job or outcome"),  # noqa: B008
    job_id: str | None = typer.Option(default=None, help="Job for an outcome"),
    statement: str | None = typer.Option(default=None, help="Outcome statement override"),
    name: str | None = typer.Option(default=None, help="Job name override"),
    importance: float | None = typer.Option(default=None, min=1.0, max=10.0),
    satisfaction: float | None = typer.Option(default=None, min=1.0, max=10.0),
    json_output: bool = JSON_OPTION,
) -> None:
    """Turn an evidence record into a Job or desired Outcome."""
    args: dict[str, Any] = {"evidence_id": evidence_id, "target": to.value}
    if job_id is not None:
        args["job_id"] = job_id
    if statement is not None:
        args["statement"] = statement
    if name is not None:
        args["name"] = name
    if importance is not None:
        args["importance"] = importance
    if satisfaction is not None:
        args["satisfaction"] = satisfaction
    noun = "Job" if to is PromoteTarget.JOB else "Outcome"
    typer.echo(
        render_saved("created", run_tool("promote_evidence", args), as_json=json_output, noun=noun)
    )
