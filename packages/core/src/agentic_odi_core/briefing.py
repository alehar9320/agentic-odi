"""The overnight briefing: what a finished run changed, as data.

A briefing is not prose. Every line points at a record the store already holds,
carrying that record's id and kind, so the surface can open the thing the line
describes. A run that changed nothing produces zero items — the honest
"nothing changed overnight" — never an invented sentence.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

#: The three things a run can report. A change is added, changed, or failed.
BriefingItemKind = Literal["added", "changed", "failed"]

ITEM_KINDS: tuple[BriefingItemKind, ...] = ("added", "changed", "failed")

#: A line is one short sentence, not a paragraph; the whole card stays readable.
MAX_TEXT_LENGTH = 200


@dataclass(frozen=True)
class BriefingItem:
    """One line of a briefing, pointing at the record it describes.

    ``text`` is written in the product's words. ``record_id`` and
    ``record_kind`` are the coordinates of the record behind the line, so the
    surface opens the record instead of trusting the sentence. An item without a
    record is not an item, so the constructor rejects one.
    """

    kind: BriefingItemKind
    text: str
    record_id: str
    record_kind: str

    def __post_init__(self) -> None:
        if self.kind not in ITEM_KINDS:
            raise ValueError(f"unknown briefing item kind: {self.kind!r}")
        text = (self.text or "").strip()
        if not text:
            raise ValueError("a briefing item needs a sentence in the product's words")
        if len(text) > MAX_TEXT_LENGTH:
            raise ValueError(f"a briefing line must be at most {MAX_TEXT_LENGTH} characters")
        if not (self.record_id or "").strip():
            raise ValueError("a briefing item must point at a record: record_id is required")
        if not (self.record_kind or "").strip():
            raise ValueError("a briefing item must name the record's kind: record_kind is required")
        if text == self.record_id:
            raise ValueError("a briefing line is prose, not a raw record id")
        # Normalise so an item built with padded whitespace compares equal.
        object.__setattr__(self, "text", text)

    def to_dict(self) -> dict[str, str]:
        return {
            "kind": self.kind,
            "text": self.text,
            "record_id": self.record_id,
            "record_kind": self.record_kind,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> BriefingItem:
        return cls(
            kind=data["kind"],
            text=data["text"],
            record_id=data["record_id"],
            record_kind=data["record_kind"],
        )


@dataclass(frozen=True)
class Briefing:
    """One run's briefing: the items, in a stable order, and when it was made.

    An empty ``items`` tuple is a real briefing — the run finished and changed
    nothing. The surface renders that as "Nothing changed overnight" instead of
    inventing a line.
    """

    run_id: str
    created_at: datetime
    items: tuple[BriefingItem, ...] = ()

    @property
    def has_items(self) -> bool:
        return len(self.items) > 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "created_at": self.created_at.isoformat(),
            "items": [item.to_dict() for item in self.items],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Briefing:
        created_at = data["created_at"]
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        return cls(
            run_id=data["run_id"],
            created_at=created_at,
            items=tuple(BriefingItem.from_dict(item) for item in data.get("items", ())),
        )


@dataclass(frozen=True)
class RunChange:
    """One change a run produced, before it is phrased as a briefing line."""

    kind: BriefingItemKind
    text: str
    record_id: str
    record_kind: str


@dataclass(frozen=True)
class RunResult:
    """What a finished run hands to :func:`build_briefing`.

    ``changes`` defaults to empty: a run that produced no structured changes
    yields an empty briefing rather than a fabricated one.
    """

    run_id: str
    changes: tuple[RunChange, ...] = ()
    created_at: datetime | None = None


def build_briefing(run_result: RunResult) -> Briefing:
    """Turn a finished run into a briefing.

    Order is the run's own order, so the same run always reads the same way. A
    change whose record is missing an id or kind is rejected by
    :class:`BriefingItem` rather than rendered as free text standing in for data.
    """
    if not (run_result.run_id or "").strip():
        raise ValueError("a briefing belongs to a run: run_id is required")
    created_at = run_result.created_at or datetime.now(timezone.utc)
    items = tuple(
        BriefingItem(
            kind=change.kind,
            text=change.text,
            record_id=change.record_id,
            record_kind=change.record_kind,
        )
        for change in run_result.changes
    )
    return Briefing(run_id=run_result.run_id, created_at=created_at, items=items)


def changes_from_summary(summary: Sequence[Mapping[str, Any]] | None) -> tuple[RunChange, ...]:
    """Read structured changes a run recorded, if any.

    Today the scheduler stores a human ``result_summary`` string and no
    structured changes, so this returns an empty tuple and the briefing is
    honestly empty. When an executor records changes, they arrive here.
    """
    if not summary:
        return ()
    return tuple(
        RunChange(
            kind=change["kind"],
            text=change["text"],
            record_id=change["record_id"],
            record_kind=change["record_kind"],
        )
        for change in summary
    )
