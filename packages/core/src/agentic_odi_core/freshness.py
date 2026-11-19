"""Staleness for derived artifacts.

A segment or a strategy is computed from the store at one revision and then kept.
Re-score an outcome afterwards and the stored verdict still reads as today's
answer unless something records which revision produced it. This module is that
something: the artifact carries ``computed_at_event_id``, and staleness is
computed when it is read, never written back.

An artifact with no stamp is *unknown*, not fresh: it was derived before the
stamp existed, so the store cannot vouch for it either way.
"""

from __future__ import annotations

from typing import Protocol


class _Stamped(Protocol):
    """Anything that records the store revision it was derived from."""

    computed_at_event_id: int | None


def is_stale(artifact: _Stamped, current_event_id: int) -> bool:
    """True when ``artifact`` was derived from an older store revision.

    ``None`` counts as stale: an unstamped artifact is one the store cannot
    vouch for, and reading it as current would be the silent staleness this
    exists to prevent.
    """
    stamp = artifact.computed_at_event_id
    if stamp is None:
        return True
    return stamp < current_event_id
