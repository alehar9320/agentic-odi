"""Local, inspectable memory for the Living Studio.

The Studio remembers the product manager across sessions: what was said, and
what the agent believes about the person and their opportunity. Observations
are proposed by the agent and confirmed, edited, or dismissed by the PM. Only
confirmed observations are treated as durable truth in the prompt.

The store is deliberately small and boring: stdlib ``sqlite3``, one file under
``~/.agentic-odi`` (overridable with ``AGENTIC_ODI_STUDIO_DB``), no network.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

OBSERVATION_KINDS: frozenset[str] = frozenset(
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
OBSERVATION_STATUSES: frozenset[str] = frozenset({"suggested", "confirmed", "dismissed"})
TURN_ROLES: frozenset[str] = frozenset({"user", "assistant", "system", "tool"})

MAX_TEXT = 2_000
MAX_CONTEXT_TEXT = 500
MAX_CONTEXT_CHARS = 4_000
MAX_SUGGESTED_IN_CONTEXT = 10


class MemoryError(ValueError):
    """Base class for recoverable memory errors."""


class ObservationNotFoundError(MemoryError):
    pass


class ConversationNotFoundError(MemoryError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_db_path() -> Path:
    configured = os.environ.get("AGENTIC_ODI_STUDIO_DB")
    if configured:
        return Path(configured)
    return Path.home() / ".agentic-odi" / "studio.db"


@dataclass
class Conversation:
    id: str
    title: str
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class Turn:
    id: int
    conversation_id: str
    role: str
    content: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "role": self.role,
            "content": self.content,
            "created_at": self.created_at,
        }


@dataclass
class Observation:
    id: str
    kind: str
    text: str
    data: dict[str, Any] = field(default_factory=dict)
    status: str = "suggested"
    confidence: float = 0.5
    source_turn: int | None = None
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "text": self.text,
            "data": self.data,
            "status": self.status,
            "confidence": self.confidence,
            "source_turn": self.source_turn,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


_SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS turns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS turns_by_conversation ON turns(conversation_id);

CREATE TABLE IF NOT EXISTS observations (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    text TEXT NOT NULL,
    data TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'suggested',
    confidence REAL NOT NULL DEFAULT 0.5,
    source_turn INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS observations_by_status ON observations(status);
"""


def _validate_text(text: str) -> str:
    cleaned = text.strip()
    if not cleaned:
        raise MemoryError("observation text cannot be empty")
    if len(cleaned) > MAX_TEXT:
        raise MemoryError(f"observation text cannot exceed {MAX_TEXT} characters")
    return cleaned


def _validate_kind(kind: str) -> str:
    if kind not in OBSERVATION_KINDS:
        raise MemoryError(f"unknown observation kind: {kind}")
    return kind


def _validate_status(status: str) -> str:
    if status not in OBSERVATION_STATUSES:
        raise MemoryError(f"unknown observation status: {status}")
    return status


def _validate_confidence(confidence: float) -> float:
    value = float(confidence)
    if not 0.0 <= value <= 1.0:
        raise MemoryError("confidence must be between 0 and 1")
    return value


def _validate_data(data: dict[str, Any] | None) -> dict[str, Any]:
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise MemoryError("observation data must be an object")
    return data


class StudioMemory:
    """A small SQLite store for conversations, turns, and observations."""

    def __init__(self, path: str | Path | None = None) -> None:
        resolved = default_db_path() if path is None else path
        self._memory = str(resolved) == ":memory:"
        self.db_path = Path(":memory:") if self._memory else Path(resolved)
        if not self._memory:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._lock = threading.RLock()
        self._connection = sqlite3.connect(
            ":memory:" if self._memory else str(self.db_path),
            check_same_thread=False,
        )
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        if not self._memory:
            self._connection.execute("PRAGMA journal_mode = WAL")
        with self._connection:
            self._connection.executescript(_SCHEMA)

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    # -- conversations -----------------------------------------------------

    def create_conversation(self, title: str = "") -> Conversation:
        conversation = Conversation(
            id=uuid.uuid4().hex,
            title=title.strip(),
            created_at=_now(),
            updated_at=_now(),
        )
        with self._lock, self._connection:
            self._connection.execute(
                "INSERT INTO conversations (id, title, created_at, updated_at) "
                "VALUES (?, ?, ?, ?)",
                (
                    conversation.id,
                    conversation.title,
                    conversation.created_at,
                    conversation.updated_at,
                ),
            )
        return conversation

    def get_conversation(self, conversation_id: str) -> Conversation | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM conversations WHERE id = ?", (conversation_id,)
            ).fetchone()
        return None if row is None else self._conversation_from_row(row)

    def latest_conversation(self) -> Conversation | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM conversations ORDER BY updated_at DESC, created_at DESC LIMIT 1"
            ).fetchone()
        return None if row is None else self._conversation_from_row(row)

    def append_turn(self, conversation_id: str, role: str, content: str) -> None:
        if role not in TURN_ROLES:
            raise MemoryError(f"unknown turn role: {role}")

        now = _now()
        with self._lock, self._connection:
            exists = self._connection.execute(
                "SELECT 1 FROM conversations WHERE id = ?", (conversation_id,)
            ).fetchone()
            if exists is None:
                raise ConversationNotFoundError(conversation_id)

            self._connection.execute(
                "INSERT INTO turns (conversation_id, role, content, created_at) "
                "VALUES (?, ?, ?, ?)",
                (conversation_id, role, content, now),
            )

            title = ""
            if role == "user" and content.strip():
                title = content.strip()[:80]
            if title:
                self._connection.execute(
                    "UPDATE conversations SET title = ?, updated_at = ? "
                    "WHERE id = ? AND title = ''",
                    (title, now, conversation_id),
                )
            self._connection.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (now, conversation_id),
            )

    def list_turns(self, conversation_id: str) -> list[Turn]:
        with self._lock:
            exists = self._connection.execute(
                "SELECT 1 FROM conversations WHERE id = ?", (conversation_id,)
            ).fetchone()
            if exists is None:
                raise ConversationNotFoundError(conversation_id)
            rows = self._connection.execute(
                "SELECT * FROM turns WHERE conversation_id = ? ORDER BY id ASC",
                (conversation_id,),
            ).fetchall()
        return [self._turn_from_row(row) for row in rows]

    # -- observations ------------------------------------------------------

    def list_observations(self, include_dismissed: bool = False) -> list[Observation]:
        query = "SELECT * FROM observations"
        params: tuple[Any, ...] = ()
        if not include_dismissed:
            query += " WHERE status != ?"
            params = ("dismissed",)
        query += " ORDER BY created_at ASC, rowid ASC"
        with self._lock:
            rows = self._connection.execute(query, params).fetchall()
        return [self._observation_from_row(row) for row in rows]

    def add_observation(
        self,
        kind: str,
        text: str,
        data: dict[str, Any] | None = None,
        status: str = "suggested",
        confidence: float = 0.5,
        source_turn: int | None = None,
    ) -> Observation:
        now = _now()
        observation = Observation(
            id=uuid.uuid4().hex,
            kind=_validate_kind(kind),
            text=_validate_text(text),
            data=_validate_data(data),
            status=_validate_status(status),
            confidence=_validate_confidence(confidence),
            source_turn=source_turn,
            created_at=now,
            updated_at=now,
        )
        with self._lock, self._connection:
            self._connection.execute(
                "INSERT INTO observations "
                "(id, kind, text, data, status, confidence, source_turn, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    observation.id,
                    observation.kind,
                    observation.text,
                    json.dumps(observation.data),
                    observation.status,
                    observation.confidence,
                    observation.source_turn,
                    observation.created_at,
                    observation.updated_at,
                ),
            )
        return observation

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
            updates["text"] = _validate_text(text)
        if status is not None:
            updates["status"] = _validate_status(status)
        if data is not None:
            updates["data"] = json.dumps(_validate_data(data))
        if confidence is not None:
            updates["confidence"] = _validate_confidence(confidence)

        with self._lock, self._connection:
            row = self._connection.execute(
                "SELECT * FROM observations WHERE id = ?", (observation_id,)
            ).fetchone()
            if row is None:
                raise ObservationNotFoundError(observation_id)

            if updates:
                updates["updated_at"] = _now()
                assignments = ", ".join(f"{column} = ?" for column in updates)
                self._connection.execute(
                    f"UPDATE observations SET {assignments} WHERE id = ?",
                    (*updates.values(), observation_id),
                )
            row = self._connection.execute(
                "SELECT * FROM observations WHERE id = ?", (observation_id,)
            ).fetchone()
        return self._observation_from_row(row)

    def delete_observation(self, observation_id: str) -> None:
        with self._lock, self._connection:
            cursor = self._connection.execute(
                "DELETE FROM observations WHERE id = ?", (observation_id,)
            )
            if cursor.rowcount == 0:
                raise ObservationNotFoundError(observation_id)

    def clear_memory(self) -> None:
        with self._lock, self._connection:
            self._connection.execute("DELETE FROM turns")
            self._connection.execute("DELETE FROM observations")
            self._connection.execute("DELETE FROM conversations")

    # -- prompt context ----------------------------------------------------

    def memory_context(self) -> str:
        """A bounded block of remembered context for the system prompt."""
        observations = self.list_observations(include_dismissed=False)
        confirmed = [item for item in observations if item.status == "confirmed"]
        suggested = [item for item in observations if item.status == "suggested"][
            :MAX_SUGGESTED_IN_CONTEXT
        ]

        lines: list[str] = []
        for item in [*confirmed, *suggested]:
            text = item.text[:MAX_CONTEXT_TEXT]
            lines.append(f"- ({item.status}) [{item.kind}] {text}")

        if not lines:
            return ""

        block = (
            "What you already know about this product manager, from earlier "
            "conversations. Use it naturally; do not recite it back or mention "
            "that you have a memory store. Confirmed items are durable context. "
            "Suggested items are your working guesses and may be wrong.\n" + "\n".join(lines)
        )
        return block[:MAX_CONTEXT_CHARS]

    # -- row mapping -------------------------------------------------------

    @staticmethod
    def _conversation_from_row(row: sqlite3.Row) -> Conversation:
        return Conversation(
            id=row["id"], title=row["title"], created_at=row["created_at"], updated_at=row["updated_at"]
        )

    @staticmethod
    def _turn_from_row(row: sqlite3.Row) -> Turn:
        return Turn(
            id=row["id"],
            conversation_id=row["conversation_id"],
            role=row["role"],
            content=row["content"],
            created_at=row["created_at"],
        )

    @staticmethod
    def _observation_from_row(row: sqlite3.Row) -> Observation:
        try:
            data = json.loads(row["data"])
        except (TypeError, json.JSONDecodeError):
            data = {}
        return Observation(
            id=row["id"],
            kind=row["kind"],
            text=row["text"],
            data=data if isinstance(data, dict) else {},
            status=row["status"],
            confidence=row["confidence"],
            source_turn=row["source_turn"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


__all__ = [
    "MAX_CONTEXT_CHARS",
    "MAX_SUGGESTED_IN_CONTEXT",
    "OBSERVATION_KINDS",
    "OBSERVATION_STATUSES",
    "Conversation",
    "ConversationNotFoundError",
    "MemoryError",
    "Observation",
    "ObservationNotFoundError",
    "StudioMemory",
    "Turn",
    "default_db_path",
]
