"""Know: did it work — the Monday digest and the spine status.

Signals live in one inbox (see :mod:`agentic_odi_cli.signals`); the know kinds
are recorded into it by the emission pass, never invented here. The digest is
deterministic markdown over that inbox, and the spine status shows where the
end-to-end evidence chain stops.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from typing import Any

import typer

from agentic_odi_cli.backend import run_tool

know_app = typer.Typer(help="The digest and the evidence spine.")

JSON_OPTION = typer.Option(False, "--json", help="Emit machine-readable JSON.")

_KIND_ORDER = ("bet_due", "score_moved", "decision_superseded", "coverage_gap")
_KIND_TITLES = {
    "bet_due": "Bets due",
    "score_moved": "Scores moved",
    "decision_superseded": "Decisions superseded",
    "coverage_gap": "Coverage gaps",
}
_EMPTY_DIGEST = "No changes in this period."

#: The spine stages, in the order a person walks them.
_SPINE_STAGES = ("captured", "scored", "decided", "bet", "measured")


def _parse_since(raw: str) -> datetime:
    """Parse a ``--since`` window: ``7d``, ``24h`` or an ISO date."""
    text = raw.strip().lower()
    now = datetime.now(timezone.utc)
    if text.endswith("d") and text[:-1].isdigit():
        days = int(text[:-1])
        if days <= 0:
            raise typer.BadParameter("--since must be a positive window")
        return now - timedelta(days=days)
    if text.endswith("h") and text[:-1].isdigit():
        hours = int(text[:-1])
        if hours <= 0:
            raise typer.BadParameter("--since must be a positive window")
        return now - timedelta(hours=hours)
    try:
        parsed = date.fromisoformat(text)
    except ValueError as exc:
        raise typer.BadParameter("--since must look like 7d, 24h or YYYY-MM-DD") from exc
    return datetime(parsed.year, parsed.month, parsed.day, tzinfo=timezone.utc)


def _should_notify(signal: dict[str, Any], rules: dict[str, dict[str, Any]]) -> bool:
    """Mirror the shared policy from the rules the backend returned."""
    rule = rules.get(signal.get("kind", ""))
    if rule is None:
        return True
    if not rule.get("enabled", True):
        return False
    if signal.get("kind") == "score_moved":
        magnitude = signal.get("magnitude")
        return magnitude is not None and abs(magnitude) >= float(rule.get("threshold", 0.0))
    return True


def build_digest(
    signals: list[dict[str, Any]], rules: list[dict[str, Any]], *, since: datetime
) -> str:
    """Render the digest markdown for the signals inside the window.

    Only signals the notification policy allows are included; the rest stay real
    feed data, just not interruptions.
    """
    rule_map = {rule.get("kind", ""): rule for rule in rules}
    # The digest is the know view: only the four know kinds, and only those the
    # policy lets interrupt. Every other signal stays real feed data.
    window = [
        signal
        for signal in signals
        if signal.get("kind") in _KIND_ORDER
        and _within(signal, since)
        and _should_notify(signal, rule_map)
    ]
    if not window:
        return _EMPTY_DIGEST

    lines: list[str] = []
    for kind in _KIND_ORDER:
        grouped = sorted(
            (s for s in window if s.get("kind") == kind),
            key=lambda s: (str(s.get("created_at", "")), str(s.get("id", ""))),
        )
        if not grouped:
            continue
        lines.append(f"## {_KIND_TITLES[kind]}")
        lines.append("")
        for signal in grouped:
            lines.append(f"- {str(signal.get('created_at', ''))[:10]} · {signal.get('title', '')}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _parse_timestamp(value: Any) -> datetime | None:
    """Parse a stored timestamp, or ``None`` when it is not usable.

    Python 3.10's ``fromisoformat`` rejects the ``Z`` suffix that Pydantic
    writes for UTC, so normalise it first; a value we cannot read is skipped
    rather than guessed at.
    """
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _within(signal: dict[str, Any], since: datetime) -> bool:
    at = signal.get("created_at")
    if not at:
        return False
    parsed = _parse_timestamp(at)
    return parsed is not None and parsed >= since


@know_app.command("digest")
def digest_cmd(
    since: str = typer.Option("7d", "--since", help="Window: 7d, 24h or YYYY-MM-DD"),
    job_id: str | None = typer.Option(None, "--job", help="Limit to one Job"),
    out: str | None = typer.Option(None, "--out", help="Write the digest to a file"),
) -> None:
    """Write a deterministic digest of the signals in the window."""
    window_start = _parse_since(since)
    args: dict[str, Any] = {}
    if job_id is not None:
        args["job_id"] = job_id
    # Refresh the inbox first: the time-based know signals (a bet coming due, a
    # stage still uncovered) are recorded here, not invented by the digest.
    run_tool("emit_know_signals", args)
    signals = run_tool("list_signals", {"limit": 200})
    rules = run_tool("list_notification_rules", {})
    body = build_digest(
        signals if isinstance(signals, list) else [],
        rules if isinstance(rules, list) else [],
        since=window_start,
    )
    if out:
        with open(out, "w", encoding="utf-8") as handle:
            handle.write(body)
        typer.echo(f"Digest written to {out}")
    else:
        typer.echo(body, nl=False)


def _spine_rows(
    job: dict[str, Any],
    outcomes: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
    bets: list[dict[str, Any]],
) -> list[tuple[str, int, str]]:
    """Count each stage and describe its next blocker.

    Counts are cumulative reach, not a claim that one chain is closed.
    """
    scored = [o for o in outcomes if o.get("importance") is not None]
    live_decisions = [d for d in decisions if not d.get("superseded_by")]
    measured = [b for b in bets if b.get("status") == "measured"]
    counts = {
        "captured": len(outcomes),
        "scored": len(scored),
        "decided": len(live_decisions),
        "bet": len(bets),
        "measured": len(measured),
    }
    blockers = {
        "captured": "capture an outcome for this job",
        "scored": "score an outcome (importance and satisfaction)",
        "decided": "record a decision",
        "bet": "create a bet from a recorded decision",
        "measured": "measure a bet once a score exists after its date",
    }
    rows: list[tuple[str, int, str]] = []
    blocked = False
    for stage in _SPINE_STAGES:
        if counts[stage] > 0:
            rows.append((stage, counts[stage], ""))
            continue
        rows.append((stage, 0, blockers[stage] if not blocked else ""))
        blocked = True
    return rows


@know_app.command("spine")
def spine(
    job_id: str | None = typer.Option(None, "--job", help="Job to inspect"),
    json_output: bool = JSON_OPTION,
) -> None:
    """Show where the end-to-end evidence spine stops for a job."""
    jobs = run_tool("get_jobs", {})
    if not isinstance(jobs, list) or not jobs:
        typer.echo("No job yet.")
        return
    if job_id is not None:
        job = run_tool("get_job", {"job_id": job_id})
    else:
        job = sorted(jobs, key=lambda j: str(j.get("id", "")))[0]
    resolved_id = str(job.get("id", ""))
    outcomes = run_tool("get_outcomes", {"job_id": resolved_id})
    decisions = run_tool("list_decisions", {"job_id": resolved_id})
    bets = run_tool("list_bets", {"job_id": resolved_id})
    rows = _spine_rows(
        job,
        outcomes if isinstance(outcomes, list) else [],
        decisions if isinstance(decisions, list) else [],
        bets if isinstance(bets, list) else [],
    )
    if json_output:
        typer.echo(
            json.dumps([{"stage": s, "count": c, "blocker": b} for s, c, b in rows], indent=2)
        )
        return
    lines = [f"Spine for {resolved_id}", ""]
    for stage, count, blocker in rows:
        suffix = f"  → {blocker}" if blocker else ""
        lines.append(f"{stage.ljust(10)} {count}{suffix}")
    typer.echo("\n".join(lines))
