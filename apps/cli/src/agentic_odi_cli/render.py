"""Rendering helpers: human-readable by default, JSON on request.

Every renderer takes ``as_json`` so the same command can serve a person at a
terminal and a script piping into ``jq`` without a second code path.
"""

from __future__ import annotations

import json
from typing import Any

_STATEMENT_WIDTH = 60


def _json(payload: Any) -> str:
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return payload
    return json.dumps(payload, indent=2, ensure_ascii=False)


def _truncate(text: str, width: int = _STATEMENT_WIDTH) -> str:
    return text if len(text) <= width else text[: width - 1] + "…"


def _num(value: Any) -> str:
    """Render numeric scores to two decimals; pass anything else through."""
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, (int, float)):
        return f"{value:.2f}"
    return str(value)


def _block(rows: list[tuple[str, Any]]) -> str:
    """Render label/value pairs as an aligned block."""
    width = max(len(label) for label, _ in rows)
    return "\n".join(f"{label.ljust(width)}  {value}" for label, value in rows)


def _table(headers: tuple[str, ...], rows: list[tuple[str, ...]], *, empty: str) -> str:
    """Render rows under headers, or ``empty`` when there is nothing to show."""
    if not rows:
        return empty
    widths = [max(len(headers[i]), *(len(row[i]) for row in rows)) for i in range(len(headers))]
    lines = ["  ".join(headers[i].ljust(widths[i]) for i in range(len(headers)))]
    lines.append("  ".join("-" * widths[i] for i in range(len(headers))))
    lines.extend("  ".join(row[i].ljust(widths[i]) for i in range(len(headers))) for row in rows)
    return "\n".join(lines)


def render_job(job: Any, *, as_json: bool) -> str:
    """Render one Job as a labelled block or JSON."""
    if not isinstance(job, dict):
        return _json(job) if as_json else str(job)
    if as_json:
        return _json(job)
    return _block(
        [
            ("id", job.get("id", "")),
            ("name", job.get("name", "")),
            ("description", job.get("description") or ""),
        ]
    )


def render_job_list(jobs: Any, *, as_json: bool) -> str:
    """Render a Job list as an aligned table or JSON."""
    if not isinstance(jobs, list):
        return _json(jobs) if as_json else str(jobs)
    if as_json:
        return _json(jobs)
    return _table(
        ("id", "name", "description"),
        [
            (
                str(job.get("id", "")),
                _truncate(str(job.get("name", ""))),
                _truncate(str(job.get("description") or "")),
            )
            for job in jobs
        ],
        empty="No jobs found.",
    )


def render_customer_outcome(outcome: Any, *, as_json: bool) -> str:
    """Render one Customer Outcome as a labelled block or JSON."""
    if not isinstance(outcome, dict):
        return _json(outcome) if as_json else str(outcome)
    if as_json:
        return _json(outcome)

    customer = outcome.get("customer_value", {})
    business = outcome.get("business_value", {})
    rows = [
        ("id", outcome.get("id", "")),
        ("job_id", outcome.get("job_id", "")),
        ("statement", customer.get("statement", "")),
        ("direction", customer.get("direction", "")),
        ("unit", customer.get("unit_of_measure", "")),
        ("object", customer.get("object_of_control", "")),
        ("importance", _num(customer.get("importance", ""))),
        ("satisfaction", _num(customer.get("satisfaction", ""))),
        (
            "opportunity",
            _num(outcome.get("opportunity_score", customer.get("opportunity_score", ""))),
        ),
        ("category", business.get("category", "")),
        ("business", business.get("statement", "")),
    ]
    width = max(len(label) for label, _ in rows)
    return "\n".join(f"{label.ljust(width)}  {value}" for label, value in rows)


def render_customer_outcome_list(outcomes: Any, *, as_json: bool) -> str:
    """Render a Customer Outcome list as an aligned table or JSON."""
    if not isinstance(outcomes, list):
        return _json(outcomes) if as_json else str(outcomes)
    if as_json:
        return _json(outcomes)
    if not outcomes:
        return "No customer outcomes found."

    headers = ("id", "statement", "importance", "satisfaction", "opportunity")
    rows = [
        (
            str(item.get("id", "")),
            _truncate(str(item.get("customer_value", {}).get("statement", ""))),
            _num(item.get("customer_value", {}).get("importance", "")),
            _num(item.get("customer_value", {}).get("satisfaction", "")),
            _num(item.get("opportunity_score", "")),
        )
        for item in outcomes
    ]
    widths = [max(len(headers[i]), *(len(row[i]) for row in rows)) for i in range(len(headers))]
    lines = ["  ".join(headers[i].ljust(widths[i]) for i in range(len(headers)))]
    lines.append("  ".join("-" * widths[i] for i in range(len(headers))))
    lines.extend("  ".join(row[i].ljust(widths[i]) for i in range(len(headers))) for row in rows)
    return "\n".join(lines)


def render_step(step: Any, *, as_json: bool) -> str:
    """Render one Job-map Step as a labelled block or JSON."""
    if not isinstance(step, dict):
        return _json(step) if as_json else str(step)
    if as_json:
        return _json(step)
    return _block(
        [
            ("id", step.get("id", "")),
            ("job_id", step.get("job_id", "")),
            ("order", step.get("order", "")),
            ("name", step.get("name", "")),
        ]
    )


def render_step_list(steps: Any, *, as_json: bool) -> str:
    """Render a Job map as an ordered table or JSON."""
    if not isinstance(steps, list):
        return _json(steps) if as_json else str(steps)
    if as_json:
        return _json(steps)
    return _table(
        ("order", "id", "name"),
        [
            (
                str(step.get("order", "")),
                str(step.get("id", "")),
                _truncate(str(step.get("name", ""))),
            )
            for step in steps
        ],
        empty="No steps found.",
    )


def render_outcome(outcome: Any, *, as_json: bool) -> str:
    """Render one desired Outcome as a labelled block or JSON."""
    if not isinstance(outcome, dict):
        return _json(outcome) if as_json else str(outcome)
    if as_json:
        return _json(outcome)
    return _block(
        [
            ("id", outcome.get("id", "")),
            ("job_id", outcome.get("job_id", "")),
            ("step_id", outcome.get("step_id") or ""),
            ("statement", outcome.get("statement", "")),
            ("importance", _num(outcome.get("importance", ""))),
            ("satisfaction", _num(outcome.get("satisfaction", ""))),
            ("opportunity", _num(outcome.get("opportunity_score", ""))),
        ]
    )


def render_outcome_list(outcomes: Any, *, as_json: bool) -> str:
    """Render desired Outcomes as an aligned table or JSON."""
    if not isinstance(outcomes, list):
        return _json(outcomes) if as_json else str(outcomes)
    if as_json:
        return _json(outcomes)
    return _table(
        ("id", "statement", "importance", "satisfaction", "opportunity"),
        [
            (
                str(item.get("id", "")),
                _truncate(str(item.get("statement", ""))),
                _num(item.get("importance", "")),
                _num(item.get("satisfaction", "")),
                _num(item.get("opportunity_score", "")),
            )
            for item in outcomes
        ],
        empty="No outcomes found.",
    )


def render_evidence(item: Any, *, as_json: bool) -> str:
    """Render one evidence record as a labelled block or JSON."""
    if not isinstance(item, dict):
        return _json(item) if as_json else str(item)
    if as_json:
        return _json(item)
    return _block(
        [
            ("id", item.get("id", "")),
            ("source", item.get("source_name", "")),
            ("kind", item.get("source_kind", "")),
            ("item_type", item.get("item_type", "")),
            ("name", item.get("name", "")),
            ("job_id", item.get("job_id") or ""),
            ("step_id", item.get("step_id") or ""),
            ("outcome_id", item.get("outcome_id") or ""),
            ("content", item.get("content", "")),
        ]
    )


def render_evidence_list(items: Any, *, as_json: bool) -> str:
    """Render evidence records as an aligned table or JSON."""
    if not isinstance(items, list):
        return _json(items) if as_json else str(items)
    if as_json:
        return _json(items)
    return _table(
        ("id", "source", "item_type", "name"),
        [
            (
                str(item.get("id", "")),
                _truncate(str(item.get("source_name", ""))),
                _truncate(str(item.get("item_type", ""))),
                _truncate(str(item.get("name", ""))),
            )
            for item in items
        ],
        empty="No evidence found.",
    )


def render_saved(verb: str, outcome: Any, *, as_json: bool, noun: str = "Customer outcome") -> str:
    """Confirm a create/update, showing the record by default."""
    if not isinstance(outcome, dict):
        return _json(outcome) if as_json else str(outcome)
    if as_json:
        return _json(outcome)
    return f"{noun} {verb}: {outcome.get('id', '')}"


def render_deleted(outcome_id: str, *, as_json: bool, noun: str = "customer outcome") -> str:
    if as_json:
        return _json({"id": outcome_id, "deleted": True})
    return f"Deleted {noun}: {outcome_id}"


def render_score(importance: float, satisfaction: float, score: float, *, as_json: bool) -> str:
    if as_json:
        return _json(
            {"importance": importance, "satisfaction": satisfaction, "opportunity_score": score}
        )
    return f"Opportunity score: {score:.2f}"


def render_scheduled_work(item: Any, *, as_json: bool) -> str:
    if not isinstance(item, dict):
        return _json(item) if as_json else str(item)
    if as_json:
        return _json(item)
    return _block(
        [
            ("id", item.get("id", "")),
            ("name", item.get("name", "")),
            ("agent_id", item.get("agent_id", "")),
            ("trigger_type", item.get("trigger_type", "")),
            ("expression", item.get("schedule_expression", "")),
            ("status", item.get("status", "")),
            ("job_id", item.get("job_id") or ""),
            ("last_run_at", item.get("last_run_at") or ""),
            ("result", item.get("result_summary") or ""),
        ]
    )


def render_scheduled_work_list(items: Any, *, as_json: bool) -> str:
    if not isinstance(items, list):
        return _json(items) if as_json else str(items)
    if as_json:
        return _json(items)
    return _table(
        ("id", "name", "agent_id", "trigger_type", "expression", "status"),
        [
            (
                str(item.get("id", "")),
                _truncate(str(item.get("name", ""))),
                str(item.get("agent_id", "")),
                str(item.get("trigger_type", "")),
                str(item.get("schedule_expression", "")),
                str(item.get("status", "")),
            )
            for item in items
        ],
        empty="No scheduled work found.",
    )
