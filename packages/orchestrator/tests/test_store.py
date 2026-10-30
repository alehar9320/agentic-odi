from __future__ import annotations

from datetime import datetime, timezone

import pytest
from agentic_odi_openhands import SecurityRisk
from agentic_odi_orchestrator import (
    AgentRun,
    AgentRunStatus,
    ApprovalRecord,
    Decision,
    OrchestratorStore,
    WorkItem,
    WorkItemStatus,
)


def _work(key: str = "manual:1") -> WorkItem:
    return WorkItem(work_key=key, title="Fix a typo", prompt="Do it", target_alias="cloud")


def test_work_item_round_trips_and_dedupes(tmp_path) -> None:
    store = OrchestratorStore(tmp_path / "orch.db")
    work = _work()
    created, is_new = store.add_work_item(work)
    assert is_new and created.id == work.id

    duplicate, is_new = store.add_work_item(_work())
    assert not is_new
    assert duplicate.id == work.id
    assert len(store.list_work_items()) == 1
    store.close()


def test_updates_are_events_and_survive_reopen(tmp_path) -> None:
    path = tmp_path / "orch.db"
    store = OrchestratorStore(path)
    work, _ = store.add_work_item(_work())
    store.update_work_item(work.id, {"status": WorkItemStatus.RUNNING, "attempts": 1})
    run = store.add_run(AgentRun(work_item_id=work.id))
    store.update_run(run.id, {"status": AgentRunStatus.RUNNING, "conversation_id": "c-1"})
    store.record_approval(
        ApprovalRecord(
            run_id=run.id,
            action_id="a-1",
            tool_name="str_replace_editor",
            risk=SecurityRisk.LOW,
            decision=Decision.ACCEPT,
            rule_id="repo-edit",
            reason="in scope",
            args_digest="abc",
        )
    )
    store.close()

    reopened = OrchestratorStore(path)
    loaded = reopened.get_work_item(work.id)
    assert loaded is not None
    assert loaded.status == WorkItemStatus.RUNNING
    assert loaded.attempts == 1
    loaded_run = reopened.get_run(run.id)
    assert loaded_run is not None
    assert loaded_run.conversation_id == "c-1"
    assert [r.action_id for r in reopened.approvals_for_run(run.id)] == ["a-1"]
    reopened.close()


def test_second_store_sees_events_after_refresh(tmp_path) -> None:
    path = tmp_path / "orch.db"
    writer = OrchestratorStore(path)
    reader = OrchestratorStore(path)

    work, _ = writer.add_work_item(_work())
    assert reader.get_work_item(work.id) is None

    assert reader.refresh() >= 1
    assert reader.get_work_item(work.id) is not None

    writer.update_work_item(work.id, {"status": WorkItemStatus.COMPLETED})
    assert reader.refresh() >= 1
    loaded = reader.get_work_item(work.id)
    assert loaded is not None
    assert loaded.status == WorkItemStatus.COMPLETED
    writer.close()
    reader.close()


def test_latest_run_and_counts(tmp_path) -> None:
    store = OrchestratorStore(tmp_path / "orch.db")
    work, _ = store.add_work_item(_work())
    first = store.add_run(AgentRun(work_item_id=work.id, attempt=1))
    started = datetime.now(timezone.utc)
    store.update_run(first.id, {"status": AgentRunStatus.FAILED, "started_at": started})
    second = store.add_run(AgentRun(work_item_id=work.id, attempt=2))
    store.update_run(second.id, {"started_at": started})

    latest = store.latest_run(work.id)
    assert latest is not None
    assert latest.id == second.id
    assert store.counts() == {"queued": 1}
    store.close()


@pytest.mark.parametrize(
    "status,expected",
    [
        ("queued", WorkItemStatus.QUEUED),
        (WorkItemStatus.BLOCKED, WorkItemStatus.BLOCKED),
    ],
)
def test_list_filters_status(tmp_path, status, expected) -> None:
    store = OrchestratorStore(tmp_path / "orch.db")
    work, _ = store.add_work_item(_work())
    store.update_work_item(work.id, {"status": expected})
    assert [item.id for item in store.list_work_items(status=status)] == [work.id]
    store.close()


def test_spent_since_filters_by_day_and_target(tmp_path) -> None:
    store = OrchestratorStore(tmp_path / "orch.db")
    cloud_work, _ = store.add_work_item(_work("manual:cloud"))
    other_work, _ = store.add_work_item(
        WorkItem(work_key="manual:other", title="x", prompt="y", target_alias="other")
    )
    today = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)
    yesterday = datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc)
    start = datetime(2026, 10, 29, 0, 0, tzinfo=timezone.utc)
    store.add_run(AgentRun(work_item_id=cloud_work.id, cost_usd=1.5, started_at=today))
    store.add_run(AgentRun(work_item_id=cloud_work.id, cost_usd=9.0, started_at=yesterday))
    store.add_run(AgentRun(work_item_id=other_work.id, cost_usd=2.0, started_at=today))

    assert store.spent_since(start) == pytest.approx(3.5)
    assert store.spent_since(start, "cloud") == pytest.approx(1.5)
    assert store.spent_since(start, "other") == pytest.approx(2.0)
    store.close()
