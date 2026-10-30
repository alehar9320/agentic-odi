"""Export the factual case for a job (C4, ALH-35).

``odi brief export`` renders the same markdown the Studio shows and, on
request, wraps it in a self-contained HTML document. The HTML inlines the
print tokens the Studio uses for paper; it pulls in no app CSS and no network
asset, so the file opens offline and prints as it reads.

Nothing here recomputes a measurement: the brief is assembled from the records
the backend already holds, and a field nobody supplied stays ``not measured``.
"""

from __future__ import annotations

import html
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import typer

from agentic_odi_cli.backend import run_tool

brief_app = typer.Typer(help="Render the factual case for a job.")

FORMATS = ("md", "html")

JOB_ID_OPTION = typer.Option(..., "--job-id", help="Job ID to render the case for.")
FORMAT_OPTION = typer.Option("md", "--format", help="Output format: md or html.")
OUT_OPTION = typer.Option(None, "--out", help="Write to this path instead of stdout.")
GENERATED_AT_OPTION = typer.Option(
    None,
    "--generated-at",
    help="Timestamp to stamp on the brief. Defaults to the export time in UTC.",
)

# The paper rules the Studio's print.css applies, inlined so the exported file
# is standalone. Colours and margins match that sheet.
_PRINT_TOKENS = """
  @page { size: A4; margin: 14mm; }
  body {
    margin: 0 auto;
    max-width: 46rem;
    padding: 2rem 1.25rem 4rem;
    background: #fff;
    color: #111;
    font: 16px/1.6 ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
  }
  h1 { font-size: 1.6rem; line-height: 1.2; }
  h2 { margin-top: 2rem; font-size: 1.2rem; }
  h3 { margin-top: 1.4rem; font-size: 1rem; }
  code { background: #f4f4f5; padding: 0.1em 0.3em; border-radius: 4px; }
  .brief__banner {
    margin: 0 0 2rem;
    padding: 0.6rem 0.8rem;
    border: 1px solid #d4d4d8;
    border-radius: 6px;
    font-size: 0.85rem;
    color: #3f3f46;
  }
  .brief__body { white-space: pre-wrap; }
"""


def _escaped_banner(source: str) -> str:
    return (
        '<p class="brief__banner">'
        "Exported from the recorded data — a snapshot, not a live view. "
        f"Source: {html.escape(source)}."
        "</p>"
    )


def brief_to_html(markdown: str, *, source: str) -> str:
    """Wrap the brief markdown in a standalone, printable HTML document.

    The markdown is escaped and rendered as pre-wrapped text, so a quote that
    contains markup stays text instead of executing.
    """
    body = html.escape(markdown)
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        "<title>Opportunity brief</title>\n"
        f"<style>{_PRINT_TOKENS}</style>\n</head>\n<body>\n"
        f"{_escaped_banner(source)}\n"
        f'<div class="brief__body">{body}</div>\n'
        "</body>\n</html>\n"
    )


def _sources_by_outcome(evidence: list[dict[str, Any]]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for record in evidence:
        outcome_id = record.get("outcome_id")
        if not isinstance(outcome_id, str):
            continue
        name = record.get("name")
        if isinstance(name, str):
            grouped.setdefault(outcome_id, []).append(name)
    return grouped


def assemble_brief_inputs(
    job: dict[str, Any],
    outcomes: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
    *,
    generated_at: str,
) -> dict[str, Any]:
    """Shape the backend's records into the renderer's inputs.

    Every measurement is copied, never derived. ``score`` stays ``None`` when
    the record has none, so the renderer shows ``not measured``.
    """
    sources = _sources_by_outcome(evidence)
    shaped = []
    for outcome in outcomes:
        outcome_id = outcome.get("id")
        shaped.append(
            {
                "outcome_id": outcome_id,
                "statement": outcome.get("statement", ""),
                "score": outcome.get("opportunity_score"),
                "n": None,
                "method": None,
                "quote": None,
                "sources": sources.get(outcome_id, []) if isinstance(outcome_id, str) else [],
                "value_estimate": outcome.get("value_estimate"),
                "value_unit": outcome.get("value_unit"),
                "value_basis": outcome.get("value_basis") or "estimate",
                "value_n": outcome.get("value_n"),
                "value_source": outcome.get("value_source"),
            }
        )
    consideration = None
    if decisions:
        latest = decisions[-1]
        chosen = latest.get("chosen_outcome_ids") or []
        consideration = f"Recorded decision {latest.get('id')} chose {', '.join(chosen)}."
    return {
        "job_id": job.get("id", ""),
        "job_name": job.get("name", ""),
        "generated_at": generated_at,
        "outcomes": shaped,
        "decision_consideration": consideration,
        "evidence_count": len(evidence),
    }


def _render(brief_inputs: dict[str, Any]) -> str:
    from agentic_odi_core import BriefInput, BriefOutcome, render_brief

    outcomes = tuple(
        BriefOutcome(
            outcome_id=item["outcome_id"],
            statement=item["statement"],
            score=item["score"],
            n=item["n"],
            method=item["method"],
            quote=item["quote"],
            sources=tuple(item["sources"]),
            value_estimate=item.get("value_estimate"),
            value_unit=item.get("value_unit"),
            value_basis=item.get("value_basis") or "estimate",
            value_n=item.get("value_n"),
            value_source=item.get("value_source"),
        )
        for item in brief_inputs["outcomes"]
    )
    brief = BriefInput(
        job_id=brief_inputs["job_id"],
        job_name=brief_inputs["job_name"],
        generated_at=brief_inputs["generated_at"],
        outcomes=outcomes,
        decision_consideration=brief_inputs["decision_consideration"],
        evidence_count=brief_inputs["evidence_count"],
    )
    return render_brief(brief)


@brief_app.command("export")
def export(
    job_id: str = JOB_ID_OPTION,
    output_format: str = FORMAT_OPTION,
    out: Path | None = OUT_OPTION,
    generated_at: str | None = GENERATED_AT_OPTION,
) -> None:
    """Render the factual case and print its path (or write it to stdout)."""
    fmt = output_format.lower()
    if fmt not in FORMATS:
        typer.echo(f"Error: unknown format '{output_format}', expected md or html", err=True)
        raise typer.Exit(code=1)

    stamped_at = generated_at or datetime.now(timezone.utc).isoformat()
    job = run_tool("get_job", {"job_id": job_id})
    if not isinstance(job, dict):
        typer.echo(f"Error: Job with ID {job_id} not found.", err=True)
        raise typer.Exit(code=1)
    outcomes = run_tool("get_outcomes", {"job_id": job_id})
    evidence = run_tool("list_evidence", {"job_id": job_id})
    decisions = run_tool("list_decisions", {"job_id": job_id})

    brief_inputs = assemble_brief_inputs(
        job,
        outcomes if isinstance(outcomes, list) else [],
        evidence if isinstance(evidence, list) else [],
        decisions if isinstance(decisions, list) else [],
        generated_at=stamped_at,
    )
    markdown = _render(brief_inputs)
    document = markdown if fmt == "md" else brief_to_html(markdown, source=f"job {job_id}")

    if out is None:
        typer.echo(document, nl=False)
        return
    out.write_text(document, encoding="utf-8")
    typer.echo(str(out))
