"""ALH-196 (M2-03.1) — the shape of a bulk change.

A bulk run is a loop over the single-item paths, so this module holds only what that loop
needs and nothing about writing: the report every surface shows, and the before/after images
of the three fields a bulk change owns. An undo is the same pair read backwards.

The fields compare as sets where order carries no meaning (``theme_ids``, ``tags``), so a row
whose memberships merely arrived in a different order is not reported as changed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agentic_odi_core.models import Outcome

#: The only fields a bulk change owns. Scores and statements are never bulk-edited:
#: a score carries signal semantics, and a statement is argued one outcome at a time.
BULK_FIELDS = ("step_id", "theme_ids", "tags")


@dataclass
class BulkReport:
    """What a bulk run asked for, wrote, refused, and — if it wrote — how to take it back."""

    requested: int
    changed: list[str] = field(default_factory=list)
    skipped: list[dict[str, str]] = field(default_factory=list)
    changes: list[dict[str, Any]] = field(default_factory=list)
    undo_token: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "requested": self.requested,
            "changed": self.changed,
            "skipped": self.skipped,
            "changes": self.changes,
            "undo_token": self.undo_token,
        }


def image(outcome: Outcome) -> dict[str, Any]:
    """The bulk-owned fields of one outcome, as data."""
    return {
        "step_id": outcome.step_id,
        "theme_ids": list(outcome.theme_ids),
        "tags": list(outcome.tags),
    }


def _same(field_name: str, before: Any, after: Any) -> bool:
    if field_name == "step_id":
        return before == after
    return set(before or []) == set(after or [])


def changed_fields(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    return [name for name in BULK_FIELDS if not _same(name, before[name], after[name])]


def theme_delta(before: list[str], after: list[str]) -> tuple[list[str], list[str]]:
    """The membership event's (added, removed) pair for one row."""
    current, target = set(before), set(after)
    added = [theme_id for theme_id in after if theme_id not in current]
    removed = [theme_id for theme_id in before if theme_id not in target]
    return added, removed


def _combine(current: list[str], keep: list[str], additions: list[str]) -> list[str]:
    """Keep what stays, in order, then append what arrives once."""
    out = [item for item in current if item in set(keep)]
    out += [item for item in additions if item not in out]
    return out


def apply_themes(current: list[str], add: list[str], remove: list[str]) -> list[str]:
    return _combine(current, [t for t in current if t not in set(remove)], add)


def apply_tags(current: list[str], add: list[str]) -> list[str]:
    return _combine(current, current, add)
