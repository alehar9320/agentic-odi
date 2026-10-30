"""Append-only event store for orchestrator state.

Every mutation is an event; the in-memory projections are rebuilt by replaying
those events. A long-running daemon calls :meth:`refresh` each tick so work
added by a separate ``odi orchestrate add`` process becomes visible without a
restart. WAL and a busy timeout mirror ``IntentStore`` so a short-lived CLI
read never blocks the daemon.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agentic_odi_orchestrator import config
from agentic_odi_orchestrator.models import (
    AgentRun,
    AgentRunStatus,
    ApprovalRecord,
    WorkItem,
    WorkItemStatus,
    serialize,
)

WORK_ITEM_CREATED = "work_item_created"
WORK_ITEM_UPDATED = "work_item_updated"
AGENT_RUN_CREATED = "agent_run_created"
AGENT_RUN_UPDATED = "agent_run_updated"
APPROVAL_RECORDED = "approval_recorded"


class OrchestratorStore:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.path = Path(db_path) if db_path else config.db_path()
        if str(self.path) == ":memory:":
            self.path = Path(":memory:")
        else:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            try:
                self.path.parent.chmod(0o700)
            except OSError:  # pragma: no cover
                pass
        self._lock = threading.RLock()
        self.conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA busy_timeout=5000;")
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS orchestrator_events (
                rowid INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL UNIQUE,
                timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                payload TEXT NOT NULL
            )
            """
        )
        if str(self.path) != ":memory:":
            try:
                self.path.chmod(0o600)
            except OSError:  # pragma: no cover
                pass
        self._reset()
        self.refresh()

    # -- replay ---------------------------------------------------------

    def _reset(self) -> None:
        self._work_items: dict[str, WorkItem] = {}
        self._work_by_key: dict[str, str] = {}
        self._runs: dict[str, AgentRun] = {}
        self._approvals: dict[str, ApprovalRecord] = {}
        self._approvals_by_run: dict[str, list[str]] = {}
        self._last_rowid = 0

    def refresh(self) -> int:
        """Apply events appended by this or another process."""
        applied = 0
        with self._lock:
            rows = self.conn.execute(
                """
                SELECT rowid, event_type, payload
                FROM orchestrator_events
                WHERE rowid > ?
                ORDER BY rowid
                """,
                (self._last_rowid,),
            ).fetchall()
            for rowid, event_type, payload in rows:
                self._apply(event_type, json.loads(payload))
                self._last_rowid = rowid
                applied += 1
        return applied

    def _apply(self, event_type: str, payload: dict[str, Any]) -> None:
        if event_type == WORK_ITEM_CREATED:
            work = WorkItem.model_validate(payload)
            if work.work_key in self._work_by_key:
                return
            self._work_items[work.id] = work
            self._work_by_key[work.work_key] = work.id
        elif event_type == WORK_ITEM_UPDATED:
            work_id = payload["id"]
            existing = self._work_items.get(work_id)
            if existing is None:
                return
            merged = {**existing.model_dump(mode="json"), **payload.get("changes", {})}
            updated = WorkItem.model_validate(merged)
            self._work_items[work_id] = updated
            self._work_by_key[updated.work_key] = work_id
        elif event_type == AGENT_RUN_CREATED:
            run = AgentRun.model_validate(payload)
            self._runs[run.id] = run
        elif event_type == AGENT_RUN_UPDATED:
            run_id = payload["id"]
            existing_run = self._runs.get(run_id)
            if existing_run is None:
                return
            merged = {**existing_run.model_dump(mode="json"), **payload.get("changes", {})}
            self._runs[run_id] = AgentRun.model_validate(merged)
        elif event_type == APPROVAL_RECORDED:
            record = ApprovalRecord.model_validate(payload)
            if record.id in self._approvals:
                return
            self._approvals[record.id] = record
            self._approvals_by_run.setdefault(record.run_id, []).append(record.id)

    def _append(self, event_type: str, payload: dict[str, Any]) -> None:
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO orchestrator_events (event_id, timestamp, event_type, payload)
                VALUES (?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    datetime.now(timezone.utc).isoformat(),
                    event_type,
                    json.dumps(serialize(payload)),
                ),
            )
        self.refresh()

    # -- work items -----------------------------------------------------

    def add_work_item(self, work: WorkItem) -> tuple[WorkItem, bool]:
        with self._lock:
            existing_id = self._work_by_key.get(work.work_key)
            if existing_id is not None:
                return self._work_items[existing_id], False
            self._append(WORK_ITEM_CREATED, work.model_dump(mode="json"))
            return self._work_items[work.id], True

    def update_work_item(self, work_id: str, changes: dict[str, Any]) -> WorkItem:
        with self._lock:
            existing = self._work_items.get(work_id)
            if existing is None:
                raise KeyError(work_id)
            changes = {**changes, "updated_at": datetime.now(timezone.utc)}
            merged = {**existing.model_dump(mode="json"), **serialize(changes)}
            candidate = WorkItem.model_validate(merged)
            self._append(
                WORK_ITEM_UPDATED,
                {"id": work_id, "changes": serialize(changes)},
            )
            return candidate

    def get_work_item(self, work_id: str) -> WorkItem | None:
        with self._lock:
            return self._work_items.get(work_id)

    def get_work_item_by_key(self, work_key: str) -> WorkItem | None:
        with self._lock:
            work_id = self._work_by_key.get(work_key)
            return self._work_items.get(work_id) if work_id else None

    def list_work_items(
        self,
        status: WorkItemStatus | str | None = None,
        *,
        source_kind: str | None = None,
        limit: int | None = None,
    ) -> list[WorkItem]:
        with self._lock:
            items = list(self._work_items.values())
        if status is not None:
            value = status.value if isinstance(status, WorkItemStatus) else str(status)
            items = [item for item in items if item.status.value == value]
        if source_kind is not None:
            items = [item for item in items if item.source_kind.value == source_kind]
        items.sort(key=lambda item: (-item.priority, item.created_at))
        return items[:limit] if limit is not None else items

    def due_work_items(self, now: datetime) -> list[WorkItem]:
        with self._lock:
            items = [
                item
                for item in self._work_items.values()
                if item.status == WorkItemStatus.QUEUED and item.due(now)
            ]
        items.sort(key=lambda item: (-item.priority, item.created_at))
        return items

    # -- runs -----------------------------------------------------------

    def add_run(self, run: AgentRun) -> AgentRun:
        with self._lock:
            self._append(AGENT_RUN_CREATED, run.model_dump(mode="json"))
            return self._runs[run.id]

    def update_run(self, run_id: str, changes: dict[str, Any]) -> AgentRun:
        with self._lock:
            existing = self._runs.get(run_id)
            if existing is None:
                raise KeyError(run_id)
            merged = {**existing.model_dump(mode="json"), **serialize(changes)}
            candidate = AgentRun.model_validate(merged)
            self._append(AGENT_RUN_UPDATED, {"id": run_id, "changes": serialize(changes)})
            return candidate

    def get_run(self, run_id: str) -> AgentRun | None:
        with self._lock:
            return self._runs.get(run_id)

    def list_runs(
        self,
        work_item_id: str | None = None,
        *,
        statuses: frozenset[AgentRunStatus] | None = None,
        limit: int | None = None,
    ) -> list[AgentRun]:
        with self._lock:
            runs = list(self._runs.values())
        if work_item_id is not None:
            runs = [run for run in runs if run.work_item_id == work_item_id]
        if statuses is not None:
            runs = [run for run in runs if run.status in statuses]
        runs.sort(key=lambda run: run.started_at or datetime.min.replace(tzinfo=timezone.utc))
        return runs[:limit] if limit is not None else runs

    def active_runs(self) -> list[AgentRun]:
        from agentic_odi_orchestrator.models import ACTIVE_RUN_STATUSES

        return self.list_runs(statuses=ACTIVE_RUN_STATUSES)

    def latest_run(self, work_item_id: str) -> AgentRun | None:
        runs = self.list_runs(work_item_id)
        return runs[-1] if runs else None

    # -- approvals ------------------------------------------------------

    def record_approval(self, record: ApprovalRecord) -> ApprovalRecord:
        with self._lock:
            if record.id in self._approvals:
                return self._approvals[record.id]
            self._append(APPROVAL_RECORDED, record.model_dump(mode="json"))
            return self._approvals[record.id]

    def approvals_for_run(self, run_id: str) -> list[ApprovalRecord]:
        with self._lock:
            ids = self._approvals_by_run.get(run_id, [])
            return [self._approvals[item] for item in ids]

    # -- reporting ------------------------------------------------------

    def counts(self) -> dict[str, int]:
        with self._lock:
            counts: dict[str, int] = {}
            for item in self._work_items.values():
                counts[item.status.value] = counts.get(item.status.value, 0) + 1
            return counts

    def spent_since(self, start: datetime, target_alias: str | None = None) -> float:
        """Cost recorded on runs active since ``start``, optionally for one target."""
        with self._lock:
            total = 0.0
            for run in self._runs.values():
                moment = run.finished_at or run.last_polled_at or run.started_at
                if moment is None or moment < start:
                    continue
                if target_alias is not None:
                    work = self._work_items.get(run.work_item_id)
                    if work is None or work.target_alias != target_alias:
                        continue
                total += run.cost_usd
            return total

    def close(self) -> None:
        with self._lock:
            self.conn.close()
