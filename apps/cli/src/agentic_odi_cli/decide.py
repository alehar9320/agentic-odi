"""Record a decision from the CLI (C6.2, ALH-158).

``odi decide`` is argument parsing and transport only: it shapes the flags into
the ``record_decision`` tool call and prints what the service returns. The
service owns validation and supersession, so the CLI and the Studio API cannot
disagree about what a valid decision is.

Rejection reasons are repeated ``--reject OUTCOME_ID=REASON`` flags rather than
a comma-separated string, so an outcome id and a reason that contain punctuation
cannot be confused for each other.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import typer

from agentic_odi_cli.backend import run_tool

decide_app = typer.Typer(help="Record a decision with its rejected options.")

JSON_OPTION = typer.Option(False, "--json", help="Emit machine-readable JSON.")
JOB_ID_OPTION = typer.Option(..., "--job-id", help="Job the decision belongs to")
CHOOSE_OPTION = typer.Option(..., "--choose", help="Outcome ID to choose (repeatable)")
RATIONALE_OPTION = typer.Option(..., "--rationale", help="Why this choice was made")
DECIDED_BY_OPTION = typer.Option(..., "--decided-by", help="Who recorded the decision")
REJECT_OPTION = typer.Option(
    None, "--reject", help="Rejected option as OUTCOME_ID=REASON (repeatable)"
)
CONFIDENCE_OPTION = typer.Option("medium", "--confidence", help="low, medium, or high")
DECIDED_AT_OPTION = typer.Option(
    None, "--decided-at", help="ISO-8601 timestamp. Defaults to now in UTC."
)
SUPERSEDES_OPTION = typer.Option(None, "--supersedes", help="Decision ID this one replaces")
DECISION_ID_OPTION = typer.Option(..., "--decision-id", help="Decision to assemble a memo for")
MEMO_FORMATS = ("md", "html")
MEMO_FORMAT_OPTION = typer.Option("md", "--format", help="Output format: md or html.")
MEMO_OUT_OPTION = typer.Option(None, "--out", help="Write to this path instead of stdout.")
MEMO_GENERATED_AT_OPTION = typer.Option(
    None,
    "--generated-at",
    help="Timestamp stamped on the export. Defaults to the export time in UTC.",
)
MEMO_NARRATE_OPTION = typer.Option(
    False,
    "--narrate/--no-narrate",
    help=(
        "Add one labelled framing paragraph, drafted by a model and checked "
        "against the memo's own numbers. Off by default; --no-narrate is "
        "byte-identical to the factual memo."
    ),
)
CHANNEL_OPTION = typer.Option("slack", "--channel", help="slack or email")
LINK_OPTION = typer.Option(None, "--link", help="Canonical link to the full memo")
VERBOSE_OPTION = typer.Option(False, "--verbose", help="Report dropped sentences")
COPY_OPTION = typer.Option(False, "--copy", help="Copy the body to the clipboard if a tool exists")


def copy_to_clipboard(text: str) -> bool:
    """Best-effort clipboard copy using a platform tool already on the machine.

    No dependency is added: when none of the known tools is present this returns
    ``False`` and the caller prints the body instead, so ``--copy`` never fails
    the command on a machine without clipboard support.
    """
    candidates: tuple[tuple[str, list[str]], ...] = (
        ("pbcopy", []),
        ("wl-copy", []),
        ("xclip", ["-selection", "clipboard"]),
        ("clip", []),
    )
    for name, args in candidates:
        executable = shutil.which(name)
        if executable is None:
            continue
        try:
            completed = subprocess.run([executable, *args], input=text.encode(), check=False)
        except OSError:
            continue
        if completed.returncode == 0:
            return True
    return False


def parse_rejection(raw: str) -> dict[str, str]:
    """Split ``OUTCOME_ID=REASON`` into its parts.

    A missing separator or an empty outcome id is a usage error, not a decision
    with a silent empty reason.
    """
    outcome_id, separator, reason = raw.partition("=")
    outcome_id = outcome_id.strip()
    if not separator or not outcome_id:
        raise ValueError(f"expected OUTCOME_ID=REASON, got {raw!r}")
    return {"outcome_id": outcome_id, "reason": reason.strip()}


@decide_app.command("record")
def record(
    job_id: str = JOB_ID_OPTION,
    choose: list[str] = CHOOSE_OPTION,
    rationale: str = RATIONALE_OPTION,
    decided_by: str = DECIDED_BY_OPTION,
    reject: list[str] = REJECT_OPTION,
    confidence: str = CONFIDENCE_OPTION,
    decided_at: str | None = DECIDED_AT_OPTION,
    supersedes: str | None = SUPERSEDES_OPTION,
    json_output: bool = JSON_OPTION,
) -> None:
    """Record a decision, naming the options it rejected and why."""
    try:
        rejected = [parse_rejection(item) for item in reject or []]
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    args: dict[str, Any] = {
        "job_id": job_id,
        "chosen_outcome_ids": list(choose),
        "rationale": rationale,
        "decided_by": decided_by,
        "decided_at": decided_at or datetime.now(timezone.utc).isoformat(),
        "confidence": confidence,
    }
    if rejected:
        args["rejected"] = rejected
    if supersedes is not None:
        args["supersedes"] = supersedes

    decision = run_tool("record_decision", args)
    if json_output:
        typer.echo(json.dumps(decision, indent=2, ensure_ascii=False))
        return
    typer.echo(f"Decision recorded: {decision.get('id')}")
    chosen = decision.get("chosen_outcome_ids") or []
    typer.echo(f"  Chose: {', '.join(chosen)}")
    if decision.get("superseded_by"):
        typer.echo(f"  This decision was already superseded by {decision['superseded_by']}")
    predecessor = supersedes
    if predecessor:
        typer.echo(f"  Supersedes: {predecessor}")


@decide_app.command("memo")
def memo(
    decision_id: str = DECISION_ID_OPTION,
    output_format: str = MEMO_FORMAT_OPTION,
    out: Path | None = MEMO_OUT_OPTION,
    generated_at: str | None = MEMO_GENERATED_AT_OPTION,
    narrate: bool = MEMO_NARRATE_OPTION,
    json_output: bool = JSON_OPTION,
) -> None:
    """Assemble the decision memo from what is already recorded, and export it.

    With no ``--format``/``--out``/``--narrate`` this is the same markdown the
    Studio shows, byte for byte. ``--format html`` wraps it in a standalone,
    printable document that carries the export time and the store's schema
    version. ``--narrate`` adds one labelled framing paragraph through the same
    narrator ``M3-04`` uses; a sentence with an absent numeral is dropped and
    recorded rather than printed. The memo is generated on read, never stored.
    """
    fmt = output_format.lower()
    if fmt not in MEMO_FORMATS:
        typer.echo(f"Error: unknown format '{output_format}', expected md or html", err=True)
        raise typer.Exit(code=1)

    from agentic_odi_core import (
        SCHEMA_VERSION,
        Bet,
        Decision,
        Evidence,
        Outcome,
        build_memo,
        render_memo_html,
        render_memo_markdown,
    )

    raw_decision = run_tool("get_decision", {"decision_id": decision_id})
    try:
        decision = Decision.model_validate(raw_decision)
    except Exception as error:  # noqa: BLE001 - an unreadable record is "not found" here
        typer.echo(f"Error: decision not found: {decision_id}", err=True)
        raise typer.Exit(code=1) from error

    outcomes = [
        Outcome.model_validate(record)
        for record in _as_list(run_tool("get_outcomes", {"job_id": decision.job_id}))
    ]
    evidence = [
        Evidence.model_validate(record)
        for record in _as_list(run_tool("list_evidence", {"job_id": decision.job_id}))
    ]
    bets = [
        Bet.model_validate(record)
        for record in _as_list(run_tool("list_bets", {"decision_id": decision.id}))
    ]
    memo = build_memo(decision, outcomes=outcomes, evidence=evidence, bets=bets)

    narrative = _narrate_memo(memo) if narrate else None
    stamped_at = generated_at or datetime.now(timezone.utc).isoformat()
    if fmt == "html":
        document = render_memo_html(
            memo,
            source=f"decision {decision_id}",
            generated_at=stamped_at,
            schema_version=SCHEMA_VERSION,
            narrative=narrative,
        )
    else:
        document = render_memo_markdown(memo, narrative=narrative)

    if json_output:
        payload: dict[str, Any] = {"decision_id": decision_id, "markdown": document}
        if narrative is not None:
            payload["dropped"] = [
                {"sentence": drop.sentence, "reason": drop.reason} for drop in narrative.dropped
            ]
        typer.echo(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    if out is None:
        typer.echo(document, nl=False)
        return
    try:
        out.write_text(document, encoding="utf-8")
    except OSError as error:
        typer.echo(f"Error: could not write {out}: {error}", err=True)
        raise typer.Exit(code=1) from error
    typer.echo(str(out))


def _as_list(payload: Any) -> list[dict[str, Any]]:
    """A tool result as a list of records. A non-list is treated as empty."""
    return [item for item in payload if isinstance(item, dict)] if isinstance(payload, list) else []


def _narrate_memo(memo: Any) -> Any:
    """Draft and check the memo's one framing paragraph (M3-11.2/ALH-171).

    Reuses ``M3-04``'s narrator and numeral guarantee. A provider failure — or no
    provider — becomes a narrative whose drop list names it, so the factual memo
    still exports and the reader sees why the drafted block is absent.
    """
    from agentic_odi_core import DroppedSentence, Narrative, narrate_memo

    from agentic_odi_cli.narrator import OpenAINarrator

    try:
        narrator = OpenAINarrator.from_env()
    except Exception as error:  # noqa: BLE001 - no provider is a drop, not a crash
        return Narrative(dropped=(DroppedSentence("", f"no narrator configured: {error}"),))
    return narrate_memo(memo, narrator)


@decide_app.command("message")
def message(
    decision_id: str = DECISION_ID_OPTION,
    channel: str = CHANNEL_OPTION,
    link: str | None = LINK_OPTION,
    verbose: bool = VERBOSE_OPTION,
    copy: bool = COPY_OPTION,
    json_output: bool = JSON_OPTION,
) -> None:
    """Draft a short, pasteable stakeholder message from the memo."""
    args: dict[str, Any] = {"decision_id": decision_id, "channel": channel}
    if link is not None:
        args["link"] = link
    payload = run_tool("render_stakeholder_message", args)
    if json_output:
        typer.echo(json.dumps(payload, indent=2, ensure_ascii=False))
        return
    subject = payload.get("subject")
    if subject:
        typer.echo(f"Subject: {subject}")
    body = payload["body"]
    if copy:
        if copy_to_clipboard(body):
            typer.echo("Copied to clipboard.")
        else:
            typer.echo("No clipboard tool found; printing the message instead.", err=True)
    typer.echo(body)
    if verbose and payload.get("dropped"):
        typer.echo(f"(dropped for length: {', '.join(payload['dropped'])})", err=True)
