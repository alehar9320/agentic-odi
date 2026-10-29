"""The Studio's memory is the core store, not a file of its own.

The sidecar used to keep its conversations and observations in a private
SQLite database nothing else could read: the CLI saw no thread, the MCP server
saw no memory, and two installs of the same product disagreed about the same
person. Both backends now write through the event-sourced repository the
canvas already uses, so one append-only log holds jobs, outcomes, the thread,
and what the agent learned.

This class keeps the small vocabulary the agent loop and the routes were
written against — turn, tree, context block — and delegates every read and
write to :class:`agentic_odi_core.ODIService`.
"""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any, cast, get_args

from agentic_odi_core import (
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
from agentic_odi_core.models import MessageRole, ObservationCategory, ObservationStatus
from agentic_odi_core.sqlite_repository import SQLiteRepository

OBSERVATION_CATEGORIES: frozenset[str] = frozenset(get_args(ObservationCategory))
OBSERVATION_STATUSES: frozenset[str] = frozenset(get_args(ObservationStatus))
TURN_ROLES: frozenset[str] = frozenset({"user", "assistant", "system", "tool"})

MAX_TEXT = 300
MAX_CONTEXT_TEXT = 500
MAX_CONTEXT_CHARS = 4_000

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


def default_db_path() -> Path:
    """Where the pre-core Studio database lived, before it was imported here."""
    configured = os.environ.get("AGENTIC_ODI_STUDIO_DB")
    if configured:
        return Path(configured)
    return Path.home() / ".agentic-odi" / "studio.db"


def _build_service(target: Any) -> ODIService:
    """Accept whatever a caller or a test hands over and return a service over it."""
    if target is None:
        return ODIService(SQLiteRepository())
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


class StudioMemory:
    """Conversations, turns, and observations, stored as events."""

    def __init__(self, target: Any = None, *, import_legacy: bool = False) -> None:
        self.service = _build_service(target)
        if import_legacy or _is_file_store(target):
            _import_legacy(self.service, default_db_path())

    def close(self) -> None:
        """Kept for callers that closed the private store; the event log needs none."""

    # -- conversations -----------------------------------------------------

    def create_conversation(self, title: str | None = None) -> Conversation:
        return self.service.start_conversation(title=title or None)

    def get_conversation(self, conversation_id: str) -> Conversation | None:
        return self.service.repo.get_conversation(conversation_id)

    def latest_conversation(self) -> Conversation | None:
        conversations = self.service.repo.list_conversations(limit=1)
        return conversations[0] if conversations else None

    def list_conversations(self, limit: int | None = None) -> list[Conversation]:
        """Newest first. Archived threads stay listed: history is never hidden."""
        return self.service.repo.list_conversations(limit=limit)

    def append_turn(
        self,
        conversation_id: str,
        role: str,
        content: str,
        message_id: str | None = None,
        parent_id: str | None = None,
        parts: list[dict[str, Any]] | None = None,
    ) -> Message:
        if role not in TURN_ROLES:
            raise ValidationError(f"unknown turn role: {role}")
        return self.service.append_message(
            conversation_id=conversation_id,
            role=cast(MessageRole, role),
            content=content,
            parts=parts,
            message_id=message_id,
            parent_id=parent_id,
        )

    def list_turns(self, conversation_id: str) -> list[Message]:
        return self.service.conversation_thread(conversation_id)

    def conversation_tree(self, conversation_id: str) -> list[Message]:
        """Every branch, oldest first.

        A turn carries its ``parent_id``, so a second answer to the same
        question is a sibling rather than a rewrite of the thread.
        """
        return self.list_turns(conversation_id)

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
            if status not in OBSERVATION_STATUSES:
                raise ValidationError(f"unknown observation status: {status}")
            updates["status"] = status
        if data is not None:
            updates["data"] = data
        if confidence is not None:
            updates["confidence"] = confidence
        if not updates:
            return self.service.get_observation(observation_id)
        return self.service.update_observation(observation_id, updates)

    def delete_observation(self, observation_id: str) -> None:
        self.service.delete_observation(observation_id)

    # -- brief -------------------------------------------------------------

    def get_brief(self) -> Brief | None:
        return self.service.get_brief()

    def save_brief(self, values: dict[str, Any]) -> Brief:
        fields = {key: str(values.get(key, "") or "") for key in BRIEF_FIELDS}
        return self.service.save_brief(**fields)

    # -- prompt context ----------------------------------------------------

    def memory_context(self) -> str:
        """A bounded block of *confirmed* memory for the system prompt.

        A proposed observation is the agent's own guess and stays out: only
        what the person confirmed is carried forward, and a dismissed one is
        never injected again, in this session or the next.
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
    imported = path.with_suffix(path.suffix + ".imported")
    if imported.exists():
        return
    try:
        _write_legacy(service, _read_legacy(path))
    except (sqlite3.Error, KeyError, TypeError, ValueError):
        return
    path.rename(imported)


#: The pre-core Studio tables, named literally so nothing here builds SQL
#: from a value.
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
        service.repo.add_observation(
            Observation(
                id=str(observation["id"]),
                text=str(observation["text"])[:MAX_TEXT],
                category=cast(ObservationCategory, kind if kind in _LEGACY_KINDS else "other"),
                status=cast(ObservationStatus, "proposed" if status == "suggested" else status),
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
    "OBSERVATION_CATEGORIES",
    "OBSERVATION_STATUSES",
    "TURN_ROLES",
    "Conversation",
    "ConversationNotFoundError",
    "Message",
    "Observation",
    "ObservationNotFoundError",
    "StudioMemory",
    "default_db_path",
]
