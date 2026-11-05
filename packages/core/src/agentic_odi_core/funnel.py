"""The onboarding funnel: five counters, kept in this machine's event log.

A funnel is a claim about the first session — did anyone get as far as a scored
outcome? — and a claim nobody can check is an impression. These five names turn
the impression into a number that lives in the same append-only log as the
domain events it sits beside, so it needs no new table, no query language and no
vendor.

There are no network calls here and there must never be any: the acceptance
criterion for this module greps its own source for an HTTP library. The one
identifier a funnel event carries is a session id drawn fresh for each launch,
deliberately distinct from the stable per-install device id in
:func:`agentic_odi_core.events.resolve_device_id`, so measuring a session never
turns the install into a tracking target.

A counter is an observation about a person's work, so it never gets to fail that
work: every write here is best-effort, and a failure is logged and swallowed.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import pairwise
from typing import Any

from agentic_odi_core.events import DEFAULT_DEVICE, DEFAULT_WORKSPACE, Event, EventStore

log = logging.getLogger(__name__)

#: The event type a counter is written under. It is not a domain event, and the
#: replay in ``sqlite_repository._apply_event`` ignores it, which is what lets
#: the funnel share the domain log without a second one to keep in step.
FUNNEL_EVENT = "FUNNEL_EVENT"

#: A position in the log, not a sixth counter: counting restarts after the last
#: one of these. Reset is append-only because the earlier events are still true
#: about the past, and deleting is the thing an append-only log cannot take back.
FUNNEL_RESET = "FUNNEL_RESET"
RESET_MARKER = "reset"

LAUNCH = "launch"
FIRST_MESSAGE = "first_message"
FIRST_OUTCOME = "first_outcome"
FIRST_SCORE = "first_score"
RETURN_SESSION = "return_session"

#: The whole vocabulary, in funnel order. Nothing may be counted that is not
#: here, and the conversion table reads its adjacency from this order.
FUNNEL_NAMES = (LAUNCH, FIRST_MESSAGE, FIRST_OUTCOME, FIRST_SCORE, RETURN_SESSION)

#: Milestones that happen once ever, rather than once per launch.
MILESTONE_NAMES = (FIRST_MESSAGE, FIRST_OUTCOME, FIRST_SCORE)

_session: str | None = None


def new_session_id() -> str:
    """Return a fresh random id. Random, so that nothing about the machine leaks into it."""
    return uuid.uuid4().hex


def start_session() -> str:
    """Begin measuring an app session — one sidecar launch — and return its id.

    The sidecar calls this once, when it comes up. Calling it again is how a
    test says "and then the app was launched a second time".
    """
    global _session
    _session = new_session_id()
    return _session


def _current_session() -> str:
    if _session is None:
        return start_session()
    return _session


def session_id() -> str:
    """The id drawn for this process, generating one on first use."""
    return _current_session()


@dataclass(frozen=True)
class FunnelTarget:
    """Where a workspace's counters go: the log, and the identity it stamps."""

    store: EventStore | None
    workspace_id: str
    device_id: str


def target_for(carrier: Any) -> FunnelTarget:
    """Return the log a repository — or the service wrapping one — writes to.

    An in-memory repository has no event log, and nothing here is allowed to
    fail because of it: the answer to "where do I write the funnel" is simply
    ``None``, which every counting function below treats as "then don't count
    it". Reading the private stamps is confined to this one place so that no
    call site has to repeat the unpacking or guess at a default.
    """
    repository = getattr(carrier, "repo", carrier)
    return FunnelTarget(
        store=getattr(repository, "store", None),
        workspace_id=getattr(repository, "_workspace_id", DEFAULT_WORKSPACE),
        device_id=getattr(repository, "_device_id", DEFAULT_DEVICE),
    )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append(
    store: EventStore | None,
    event_type: str,
    name: str,
    *,
    workspace_id: str,
    device_id: str,
    at: str,
    session_id: str,
) -> None:
    if store is None:
        return
    try:
        store.append(
            event_type,
            {"name": name, "at": at, "session_id": session_id},
            workspace_id=workspace_id,
            device_id=device_id,
        )
    except Exception:  # noqa: BLE001  # a measurement never fails the thing it measures
        log.warning("funnel event %s could not be recorded", name, exc_info=True)


def _records(store: EventStore | None, workspace_id: str) -> list[Event]:
    """The counters this workspace's measurement can currently see.

    Reading the log is also best-effort: a store that cannot be read yields an
    empty view rather than an exception on someone's request.
    """
    if store is None:
        return []
    try:
        stream = store.get_stream(workspace_id=workspace_id)
    except Exception:  # noqa: BLE001
        log.warning("funnel events could not be read", exc_info=True)
        return []

    visible: list[Event] = []
    for event in stream:
        if event["type"] == FUNNEL_RESET:
            visible = []
        elif event["type"] == FUNNEL_EVENT:
            visible.append(event)
    return visible


def record_launch(
    store: EventStore | None,
    *,
    workspace_id: str = DEFAULT_WORKSPACE,
    device_id: str = DEFAULT_DEVICE,
    session_id: str | None = None,
    at: str | None = None,
) -> None:
    """Count this launch, and count it as a return if the workspace has been seen.

    ``launch`` is once per session; ``return_session`` is once per session, and
    only for a session that is not the first one the workspace recorded.
    """
    resolved_session = session_id if session_id is not None else _current_session()
    moment = at if at is not None else _now()
    was_known = any(
        str(event["payload"].get("name")) == LAUNCH for event in _records(store, workspace_id)
    )
    _append(
        store,
        FUNNEL_EVENT,
        LAUNCH,
        workspace_id=workspace_id,
        device_id=device_id,
        at=moment,
        session_id=resolved_session,
    )
    if was_known:
        _append(
            store,
            FUNNEL_EVENT,
            RETURN_SESSION,
            workspace_id=workspace_id,
            device_id=device_id,
            at=moment,
            session_id=resolved_session,
        )


def record_milestone(
    store: EventStore | None,
    name: str,
    *,
    workspace_id: str = DEFAULT_WORKSPACE,
    device_id: str = DEFAULT_DEVICE,
    session_id: str | None = None,
    at: str | None = None,
) -> None:
    """Record a ``first_*`` milestone — once per workspace, however often it is hit.

    The check is against the log rather than a flag in memory, so the milestone
    stays first-across-restarts. An unknown name is a programmer's error, not
    input to be filed: page views and other client-only signals are not this
    funnel's vocabulary.
    """
    if name not in MILESTONE_NAMES:
        raise ValueError(
            f"{name!r} is not a funnel milestone; the vocabulary is {', '.join(MILESTONE_NAMES)}"
        )
    already = any(
        str(event["payload"].get("name")) == name for event in _records(store, workspace_id)
    )
    if already:
        return
    _append(
        store,
        FUNNEL_EVENT,
        name,
        workspace_id=workspace_id,
        device_id=device_id,
        at=at if at is not None else _now(),
        session_id=session_id if session_id is not None else _current_session(),
    )


def reset(
    store: EventStore | None,
    *,
    workspace_id: str = DEFAULT_WORKSPACE,
    device_id: str = DEFAULT_DEVICE,
    session_id: str | None = None,
    at: str | None = None,
) -> None:
    """Start the measurement over, leaving every earlier event in the log."""
    _append(
        store,
        FUNNEL_RESET,
        RESET_MARKER,
        workspace_id=workspace_id,
        device_id=device_id,
        at=at if at is not None else _now(),
        session_id=session_id if session_id is not None else _current_session(),
    )


def stats(
    store: EventStore | None,
    *,
    workspace_id: str = DEFAULT_WORKSPACE,
) -> dict[str, dict[str, Any]]:
    """Return ``{counts, first_seen, last_seen}`` for each of the five names.

    Every name is always present, and one that has not happened says so with a
    zero and two ``None`` values — the funnel has no invented history.
    """
    records = _records(store, workspace_id)
    summary: dict[str, dict[str, Any]] = {}
    for name in FUNNEL_NAMES:
        seen = [
            str(event["payload"].get("at"))
            for event in records
            if event["payload"].get("name") == name
        ]
        summary[name] = {
            "counts": len(seen),
            "first_seen": seen[0] if seen else None,
            "last_seen": seen[-1] if seen else None,
        }
    return summary


def adjacent_conversions(summary: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Compare each step to the one before it, in funnel order.

    A conversion with nothing in its denominator is left blank rather than
    called zero: "we cannot tell yet" and "nobody got this far" are different
    facts, and the table should not confuse them.
    """
    rows: list[dict[str, Any]] = []
    for previous, following in pairwise(FUNNEL_NAMES):
        from_counts = int(summary[previous]["counts"])
        to_counts = int(summary[following]["counts"])
        rows.append(
            {
                "from": previous,
                "to": following,
                "from_counts": from_counts,
                "to_counts": to_counts,
                "conversion": (to_counts / from_counts) if from_counts else None,
            }
        )
    return rows


# -- the seam the product's own code counts through ---------------------------
#
# A hook should name the repository it is standing next to, not unpack a store,
# a workspace and a device id at every call site. These four do that unpacking
# once, and inherit the rule that a counter never fails the thing it measures.


def count_launch(carrier: Any, session_id: str | None = None) -> None:
    """Count this launch, and the return if this workspace has been launched before."""
    target = target_for(carrier)
    record_launch(
        target.store,
        workspace_id=target.workspace_id,
        device_id=target.device_id,
        session_id=session_id,
    )


def count_milestone(carrier: Any, name: str) -> None:
    """Count a ``first_*`` milestone against the carrier's log, once per workspace."""
    target = target_for(carrier)
    record_milestone(
        target.store,
        name,
        workspace_id=target.workspace_id,
        device_id=target.device_id,
    )


def count_reset(carrier: Any) -> None:
    """Restart this workspace's measurement where it stands."""
    target = target_for(carrier)
    reset(target.store, workspace_id=target.workspace_id, device_id=target.device_id)


def read_counts(carrier: Any) -> dict[str, dict[str, Any]]:
    """Return :func:`stats` for the workspace the carrier writes to."""
    target = target_for(carrier)
    return stats(target.store, workspace_id=target.workspace_id)
