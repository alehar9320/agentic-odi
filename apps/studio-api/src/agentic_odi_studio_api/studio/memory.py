"""The Studio's memory is the core store, not a file of its own.

The sidecar used to keep its conversations and observations in a private
SQLite database nothing else could read: the CLI saw no thread, the MCP server
saw no memory, and two installs of the same product disagreed about the same
person. Both backends now write through the event-sourced repository the
canvas already uses, so one append-only log holds jobs, outcomes, the thread,
and what the agent learned.

Citations come from the same place. A turn's claims are stored on the message
itself, so the evidence a reply stood behind survives a reload, a branch, and a
second client — and the citation reader below keeps the vocabulary the routes
and the tests were written against.
"""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast, get_args

from agentic_odi_core import (
    V2MOM,
    Brief,
    Conversation,
    ConversationNotFoundError,
    InMemoryRepository,
    Message,
    Observation,
    ObservationNotFoundError,
    ODIService,
    Repository,
)
from agentic_odi_core.errors import ValidationError
from agentic_odi_core.integrity import ensure_intact
from agentic_odi_core.models import MessageRole, ObservationCategory, ObservationStatus
from agentic_odi_core.sqlite_repository import SQLiteRepository

from agentic_odi_studio_api.studio.claims import Claim, EvidenceSnapshot, split_claims

OBSERVATION_CATEGORIES: frozenset[str] = frozenset(get_args(ObservationCategory))
OBSERVATION_STATUSES: frozenset[str] = frozenset(get_args(ObservationStatus))
TURN_ROLES: frozenset[str] = frozenset({"user", "assistant", "system", "tool"})

#: The word the pre-core store used for an unconfirmed observation. It maps to
#: the core's ``proposed``; nothing else is renamed.
_LEGACY_PROPOSED = "suggested"

MAX_TEXT = 300
MAX_CONTEXT_TEXT = 500
MAX_CONTEXT_CHARS = 4_000
MAX_SUGGESTED_IN_CONTEXT = 10

#: How many threads the history list carries. The switcher's full UI (#408)
#: owns paging; this slice shows the recent ones and stops.
MAX_CONVERSATIONS = 20

BRIEF_FIELDS = ("product_name", "product_url", "target_user", "job_statement", "core_problem")

#: The categories a pre-core ``kind`` could name. Anything else is imported as
#: ``other`` rather than dropped.
_LEGACY_KINDS = frozenset(
    {
        "career",
        "opportunity",
        "business",
        "stakeholder",
        "constraint",
        "evidence",
        "preference",
    }
)


class MemoryError(ValueError):
    """Base class for recoverable memory errors."""


def default_db_path() -> Path:
    """Where the pre-core Studio database lived, before it was imported here."""
    configured = os.environ.get("AGENTIC_ODI_STUDIO_DB")
    if configured:
        return Path(configured)
    return Path.home() / ".agentic-odi" / "studio.db"


@dataclass
class ConversationSummary:
    """A conversation as the history switcher sees it: metadata plus a count."""

    id: str
    title: str
    created_at: str
    updated_at: str
    head_id: str | None
    turn_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "head_id": self.head_id,
            "turn_count": self.turn_count,
        }


@dataclass
class TurnCitation:
    """One stored claim: its status, and the records it cited."""

    turn_id: str
    claim_index: int
    status: str
    evidence: list[EvidenceSnapshot] = field(default_factory=list)
    reason: str | None = None


def _claim_dict(claim: Claim) -> dict[str, Any]:
    """A claim as the event log stores it: plain JSON, one record per citation."""
    return {
        "index": claim.index,
        "text": claim.text,
        "status": claim.status,
        "evidence": [
            {
                "id": snapshot.id,
                "name": snapshot.name,
                "source_name": snapshot.source_name,
            }
            for snapshot in claim.evidence
        ],
        "reason": claim.reason,
    }


def _claim_from_dict(raw: Any) -> Claim:
    if isinstance(raw, Claim):
        return raw
    return Claim(
        index=int(raw.get("index", 0)),
        text=str(raw.get("text", "")),
        status=cast(Any, raw.get("status", "uncited")),
        evidence=tuple(EvidenceSnapshot(**item) for item in raw.get("evidence") or []),
        reason=raw.get("reason"),
    )


def _build_service(target: Any) -> ODIService:
    """Accept whatever a caller or a test hands over and return a service over it."""
    if target is None:
        # The conversation history has its own file; defaulting to the intent
        # store's path would leave a second live connection on that database.
        return ODIService(SQLiteRepository(str(default_db_path())))
    if isinstance(target, ODIService):
        return target
    if isinstance(target, (str, Path)):
        if str(target) == ":memory:":
            return ODIService(InMemoryRepository())
        return ODIService(SQLiteRepository(str(target)))
    # ``Repository`` is a static Protocol, so it cannot be isinstance-checked:
    # anything that can store a conversation is treated as one.
    if hasattr(target, "add_conversation"):
        return ODIService(cast(Repository, target))
    raise ValidationError(f"unsupported memory store: {type(target).__name__}")


def _is_file_store(target: Any) -> bool:
    """Whether this target ends up on disk, unlike an in-memory test double."""
    if isinstance(target, Path):
        return True
    if isinstance(target, str):
        return target != ":memory:"
    return target is None


def _iso(value: Any) -> str:
    if value is None:
        return ""
    if hasattr(value, "isoformat"):
        return str(value.isoformat())
    return str(value)


class StudioMemory:
    """Conversations, turns, claims, and observations, stored as events."""

    def __init__(self, target: Any = None, *, import_legacy: bool = False) -> None:
        self._closed = False
        if _is_file_store(target):
            # The default store is a file too, and a damaged one must fail here,
            # by name, before the app serves.
            path = default_db_path() if target is None else Path(str(target))
            if path.is_file():
                # A damaged file must fail here, by name, before the app serves.
                connection = sqlite3.connect(path)
                try:
                    ensure_intact(connection, str(path), label="Your Studio memory")
                finally:
                    connection.close()
        self._owns_store = target is None or isinstance(target, (str, Path))
        self.service = _build_service(target)
        if import_legacy or _is_file_store(target):
            _import_legacy(self.service, default_db_path())

    def close(self) -> None:
        """Fold the log back into the file and mark the store closed.

        A store this object opened owns its write-ahead log; folding it back on
        close is what leaves one file behind for the next launch, and it is also
        what makes a damaged file detectable on the next boot instead of hidden
        behind the log.
        """
        if self._owns_store:
            self.checkpoint("TRUNCATE")
        self._closed = True

    def checkpoint(self, mode: str = "TRUNCATE") -> None:
        """Kept for callers that checkpointed the private store."""
        repository = self.service.repo
        checkpoint = getattr(repository, "checkpoint", None)
        if callable(checkpoint):
            checkpoint(mode)

    # -- conversations -----------------------------------------------------

    def create_conversation(self, title: str | None = None) -> Conversation:
        return self.service.start_conversation(title=title or None)

    def get_conversation(self, conversation_id: str) -> Conversation | None:
        return self.service.repo.get_conversation(conversation_id)

    def latest_conversation(self) -> Conversation | None:
        conversations = self.service.repo.list_conversations(limit=1)
        return conversations[0] if conversations else None

    def list_conversations(self, limit: int | None = MAX_CONVERSATIONS) -> list[ConversationSummary]:
        """Newest first, capped, each with the number of turns it holds.

        Archived threads stay listed: history is never hidden, it is filtered by
        the client that has a reason to filter it.
        """
        conversations = self.service.repo.list_conversations(limit=None)
        ordered = sorted(conversations, key=lambda item: _iso(item.updated_at), reverse=True)
        if limit is not None:
            ordered = ordered[:limit]
        summaries: list[ConversationSummary] = []
        for conversation in ordered:
            turns = self.service.repo.list_messages(conversation.id)
            summaries.append(
                ConversationSummary(
                    id=conversation.id,
                    title=conversation.title or "",
                    created_at=conversation.created_at,
                    updated_at=conversation.updated_at,
                    head_id=conversation.head_id,
                    turn_count=len(turns),
                )
            )
        return summaries

    def set_head(self, conversation_id: str, head_id: str | None) -> Conversation:
        """Record which branch is visible, so a reload opens the same one."""
        return self._update_conversation(conversation_id, {"head_id": head_id})

    def update_title(self, conversation_id: str, title: str) -> Conversation:
        return self._update_conversation(conversation_id, {"title": title.strip()[:200]})

    def set_archived(self, conversation_id: str, archived: bool) -> Conversation:
        """Archive is reversible; only an explicit delete loses the transcript."""
        return self._update_conversation(conversation_id, {"archived": archived})

    def delete_conversation(self, conversation_id: str) -> None:
        self.service.delete_conversation(conversation_id)

    def _update_conversation(self, conversation_id: str, updates: dict[str, Any]) -> Conversation:
        if self.get_conversation(conversation_id) is None:
            raise ConversationNotFoundError(conversation_id)
        return self.service.update_conversation(conversation_id, updates)

    # -- turns -------------------------------------------------------------

    def append_turn(
        self,
        conversation_id: str,
        role: str,
        content: str,
        message_id: str | None = None,
        parent_id: str | None = None,
        parts: list[dict[str, Any]] | None = None,
    ) -> Message:
        """Record a turn and return the stored message, so citations can attach.

        The returned handle is the message itself: its id is the client-facing
        id, so ``add_citations`` and ``citations_for_turn`` take the same value
        the branch tree exposes.
        """
        if role not in TURN_ROLES:
            raise MemoryError(f"unknown turn role: {role}")
        if self.get_conversation(conversation_id) is None:
            raise ConversationNotFoundError(conversation_id)
        return self.service.append_message(
            conversation_id=conversation_id,
            role=cast(MessageRole, role),
            content=content,
            parts=parts,
            message_id=message_id,
            parent_id=parent_id,
        )

    def list_turns(self, conversation_id: str) -> list[Message]:
        if self.get_conversation(conversation_id) is None:
            raise ConversationNotFoundError(conversation_id)
        return self.service.conversation_thread(conversation_id)

    def conversation_tree(self, conversation_id: str) -> list[Message]:
        """Every branch, oldest first.

        A turn carries its ``parent_id``, so a second answer to the same
        question is a sibling rather than a rewrite of the thread.
        """
        turns = self.list_turns(conversation_id)
        restored: list[Message] = []
        for turn in turns:
            claims = self.claims_for_turn(turn)
            if claims and len(claims) != len(split_claims(turn.content)):
                # Content and citations disagree; attach none rather than the
                # wrong sentence's evidence.
                claims = []
            restored.append(turn.model_copy(update={"claims": claims}))
        return restored

    # -- citations ---------------------------------------------------------

    def add_citations(self, turn: Message | str, claims: list[Claim]) -> None:
        """Store one claim per row, idempotently, on the turn itself.

        A duplicate retry rewrites the same claims instead of stacking new ones.
        """
        message_id = turn if isinstance(turn, str) else turn.id
        self.service.repo.set_message_claims(message_id, [_claim_dict(claim) for claim in claims])

    def claims_for_turn(self, turn: Message | str) -> list[Claim]:
        """The claims this turn stands behind, in sentence order."""
        message_id = turn if isinstance(turn, str) else turn.id
        message = self.service.repo.get_message(message_id)
        if message is None:
            return []
        return [_claim_from_dict(raw) for raw in message.claims]

    def citations_for_turn(self, turn: Message | str) -> list[TurnCitation]:
        message_id = turn if isinstance(turn, str) else turn.id
        return [
            TurnCitation(
                turn_id=message_id,
                claim_index=claim.index,
                status=claim.status,
                evidence=list(claim.evidence),
                reason=claim.reason,
            )
            for claim in self.claims_for_turn(turn)
        ]

    # -- observations ------------------------------------------------------

    def list_observations(self, include_dismissed: bool = False) -> list[Observation]:
        items = self.service.list_observations()
        if include_dismissed:
            return items
        return [item for item in items if item.status != "dismissed"]

    def add_observation(
        self,
        category: str,
        text: str,
        data: dict[str, Any] | None = None,
        status: str = "proposed",
        confidence: float = 0.5,
        conversation_id: str | None = None,
        source_message_id: str | None = None,
    ) -> Observation:
        if category not in OBSERVATION_CATEGORIES:
            raise ValidationError(f"unknown observation category: {category}")
        if status == _LEGACY_PROPOSED:
            status = "proposed"
        if status not in OBSERVATION_STATUSES:
            raise ValidationError(f"unknown observation status: {status}")
        observation = self.service.remember(
            text=text.strip()[:MAX_TEXT],
            category=cast(ObservationCategory, category),
            conversation_id=conversation_id,
            source_message_id=source_message_id,
            data=data,
            confidence=confidence,
        )
        if status == "proposed":
            return observation
        return self.service.update_observation(observation.id, {"status": status})

    def update_observation(
        self,
        observation_id: str,
        *,
        text: str | None = None,
        status: str | None = None,
        data: dict[str, Any] | None = None,
        confidence: float | None = None,
    ) -> Observation:
        updates: dict[str, Any] = {}
        if text is not None:
            updates["text"] = text.strip()[:MAX_TEXT]
        if status is not None:
            if status == _LEGACY_PROPOSED:
                status = "proposed"
            if status not in OBSERVATION_STATUSES:
                raise ValidationError(f"unknown observation status: {status}")
            updates["status"] = status
        if data is not None:
            updates["data"] = data
        if confidence is not None:
            updates["confidence"] = confidence
        if not updates:
            current = self.service.get_observation(observation_id)
            if current is None:
                raise ObservationNotFoundError(observation_id)
            return current
        return self.service.update_observation(observation_id, updates)

    def delete_observation(self, observation_id: str) -> None:
        self.service.delete_observation(observation_id)

    # -- brief -------------------------------------------------------------

    def get_brief(self) -> Brief | None:
        return self.service.get_brief()

    def save_brief(self, values: dict[str, Any]) -> Brief:
        fields = {key: str(values.get(key, "") or "") for key in BRIEF_FIELDS}
        vision = values.get("v2mom")
        return self.service.save_brief(
            **fields,
            v2mom=None if vision is None else V2MOM.model_validate(vision),
        )

    # -- prompt context ----------------------------------------------------

    def memory_context(self) -> str:
        """A bounded block of *confirmed* memory for the system prompt.

        A proposed observation is the agent's own guess and stays out: only what
        the person confirmed is carried forward, and a dismissed one is never
        injected again, in this session or the next.
        """
        confirmed = self.service.confirmed_observations()
        if not confirmed:
            return ""
        lines = [f"- [{item.category}] {item.text[:MAX_CONTEXT_TEXT]}" for item in confirmed]
        block = (
            "What this product manager confirmed about themself, their product, and "
            "their customers. Treat it as durable context and use it naturally; do "
            "not recite it back or mention that you have a memory store.\n" + "\n".join(lines)
        )
        return block[:MAX_CONTEXT_CHARS]

    def clear_memory(self) -> None:
        for conversation in self.service.list_conversations():
            self.service.delete_conversation(conversation.id)
        for observation in self.service.list_observations():
            self.service.delete_observation(observation.id)


def _import_legacy(service: ODIService, path: Path) -> None:
    """Move a pre-core ``studio.db`` into the event log, once.

    The file is renamed, not deleted, so a person who wants to undo the import
    still has what the sidecar used to keep.
    """
    if not path.is_file():
        return
    # A store opened on the legacy path itself must never import (and rename)
    # the very file it is reading: that empties a live conversation log.
    live = getattr(service.repo, "db_path", None)
    if live is not None:
        try:
            if Path(str(live)).resolve() == path.resolve():
                return
        except OSError:
            return
    imported = path.with_suffix(path.suffix + ".imported")
    if imported.exists():
        return
    try:
        _write_legacy(service, _read_legacy(path))
    except (sqlite3.Error, KeyError, TypeError, ValueError):
        return
    path.rename(imported)


#: The pre-core Studio tables, named literally so nothing here builds SQL from a
#: value.
_LEGACY_QUERIES = {
    "conversations": "SELECT * FROM conversations ORDER BY rowid",
    "turns": "SELECT * FROM turns ORDER BY rowid",
    "observations": "SELECT * FROM observations ORDER BY rowid",
}


def _read_legacy(path: Path) -> dict[str, list[dict[str, Any]]]:
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        tables = {
            str(row["name"])
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        return {
            name: [dict(row) for row in connection.execute(sql)]
            for name, sql in _LEGACY_QUERIES.items()
            if name in tables
        }
    finally:
        connection.close()


def _write_legacy(service: ODIService, rows: dict[str, list[dict[str, Any]]]) -> None:
    turns = rows.get("turns", [])
    for conversation in rows.get("conversations", []):
        stored = service.repo.add_conversation(
            Conversation(
                id=str(conversation["id"]),
                title=conversation.get("title") or None,
            )
        )
        previous: str | None = None
        for index, turn in enumerate(row for row in turns if row["conversation_id"] == stored.id):
            message_id = str(turn.get("message_id") or f"{stored.id}-turn-{index + 1}")
            service.append_message(
                conversation_id=stored.id,
                role=cast(MessageRole, turn["role"]),
                content=str(turn["content"]),
                message_id=message_id,
                # The pre-core store had no branching: turns chained in row order.
                parent_id=turn.get("parent_id") or previous,
            )
            previous = message_id
        head = conversation.get("head_id")
        if head:
            service.repo.update_conversation(stored.id, {"head_id": str(head)})
    for observation in rows.get("observations", []):
        kind = str(observation.get("kind") or "other")
        status = str(observation.get("status") or "proposed")
        if status == _LEGACY_PROPOSED:
            status = "proposed"
        service.repo.add_observation(
            Observation(
                id=str(observation["id"]),
                text=str(observation["text"])[:MAX_TEXT],
                category=cast(ObservationCategory, kind if kind in _LEGACY_KINDS else "other"),
                status=cast(ObservationStatus, status),
                data=_legacy_json(observation.get("data")),
                confidence=float(observation.get("confidence") or 0.5),
            )
        )


def _legacy_json(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    try:
        parsed = json.loads(str(raw))
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


__all__ = [
    "BRIEF_FIELDS",
    "MAX_CONTEXT_CHARS",
    "MAX_CONVERSATIONS",
    "MAX_SUGGESTED_IN_CONTEXT",
    "OBSERVATION_CATEGORIES",
    "OBSERVATION_STATUSES",
    "TURN_ROLES",
    "ConversationNotFoundError",
    "ConversationSummary",
    "MemoryError",
    "ObservationNotFoundError",
    "StudioMemory",
    "TurnCitation",
    "default_db_path",
]
