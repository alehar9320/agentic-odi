"""Morning briefing assembled from a run's results."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class BriefingItem:
    kind: str
    text: str
    record_id: str
    record_kind: str

    def __init__(self, kind: str, text: str, record_id: str, record_kind: str):
        if not record_id:
            raise ValueError("BriefingItem requires a record_id")
        if not record_kind:
            raise ValueError("BriefingItem requires a record_kind")
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "text", text)
        object.__setattr__(self, "record_id", record_id)
        object.__setattr__(self, "record_kind", record_kind)


@dataclass(frozen=True)
class Briefing:
    run_id: str
    created_at: datetime | str
    items: list[BriefingItem]

    def __init__(self, run_id: str, created_at: datetime | str, items: list[BriefingItem]):
        object.__setattr__(self, "run_id", run_id)
        object.__setattr__(self, "created_at", created_at)
        object.__setattr__(self, "items", list(items))


def build_briefing(run_result: Any) -> Briefing:
    """Build a briefing from a run result.

    This is a simple implementation following the issue requirements.
    """
    from uuid import uuid4

    run_id = getattr(run_result, "run_id", None) or getattr(run_result, "id", None) or str(uuid4())
    created_at = getattr(run_result, "created_at", None) or datetime.utcnow()

    items = []
    # Extract items from run_result if present
    if hasattr(run_result, "items"):
        for item in run_result.items:
            if getattr(item, "record_id", None):  # Only items with records
                items.append(
                    BriefingItem(
                        kind=getattr(item, "kind"),
                        text=getattr(item, "text"),
                        record_id=getattr(item, "record_id"),
                        record_kind=getattr(item, "record_kind"),
                    )
                )
    elif isinstance(run_result, dict):
        for item in run_result.get("items", []):
            if item.get("record_id"):
                items.append(
                    BriefingItem(
                        kind=item["kind"],
                        text=item["text"],
                        record_id=item["record_id"],
                        record_kind=item["record_kind"],
                    )
                )

    return Briefing(run_id=run_id, created_at=created_at, items=items)
