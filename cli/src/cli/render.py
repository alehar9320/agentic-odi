"""Rendering helpers: human-readable by default, JSON on request.

Every renderer takes ``as_json`` so the same command can serve a person at a
terminal and a script piping into ``jq`` without a second code path.
"""

from __future__ import annotations

import json
from typing import Any

_STATEMENT_WIDTH = 60


def _json(payload: Any) -> str:
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


def render_customer_outcome(outcome: dict[str, Any], *, as_json: bool) -> str:
    """Render one Customer Outcome as a labelled block or JSON."""
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


def render_customer_outcome_list(outcomes: list[dict[str, Any]], *, as_json: bool) -> str:
    """Render a Customer Outcome list as an aligned table or JSON."""
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


def render_saved(verb: str, outcome: dict[str, Any], *, as_json: bool) -> str:
    """Confirm a create/update, showing the outcome block by default."""
    if as_json:
        return _json(outcome)
    return f"Customer outcome {verb}: {outcome.get('id', '')}"


def render_deleted(outcome_id: str, *, as_json: bool) -> str:
    if as_json:
        return _json({"id": outcome_id, "deleted": True})
    return f"Deleted customer outcome: {outcome_id}"


def render_score(importance: float, satisfaction: float, score: float, *, as_json: bool) -> str:
    if as_json:
        return _json(
            {"importance": importance, "satisfaction": satisfaction, "opportunity_score": score}
        )
    return f"Opportunity score: {score:.2f}"
