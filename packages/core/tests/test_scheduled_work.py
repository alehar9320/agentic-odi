import pytest
from agentic_odi_core import (
    InMemoryRepository,
    ODIService,
    RunChange,
    ScheduledWork,
    ScheduledWorkNotFoundError,
    ScheduledWorkStatus,
    ScheduledWorkTriggerType,
)


def test_schedule_work_flow():
    repo = InMemoryRepository()
    service = ODIService(repo)

    job = service.add_job("Background Cloud Job")

    work = service.schedule_work(
        name="Nightly Outcome Evaluation",
        schedule_expression="0 0 * * *",
        agent_id="eval-agent-1",
        trigger_type="cron",
        payload={"batch_size": 100},
        job_id=job.id,
    )

    assert isinstance(work, ScheduledWork)
    assert work.name == "Nightly Outcome Evaluation"
    assert work.agent_id == "eval-agent-1"
    assert work.trigger_type == ScheduledWorkTriggerType.CRON
    assert work.status == ScheduledWorkStatus.SCHEDULED
    assert work.job_id == job.id

    fetched = service.get_scheduled_work(work.id)
    assert fetched.id == work.id

    listed = service.list_scheduled_work(job_id=job.id)
    assert len(listed) == 1
    assert listed[0].id == work.id

    # Triggering dispatches the record; no executor exists, so nothing ran.
    triggered = service.trigger_scheduled_work(work.id)
    assert triggered.status == ScheduledWorkStatus.RUNNING
    assert triggered.last_run_at is not None
    assert "no executor is installed" in (triggered.result_summary or "")
    assert "successfully" not in (triggered.result_summary or "")

    # Cancel task
    work2 = service.schedule_work(name="One-time job", schedule_expression="+1h")
    cancelled = service.cancel_scheduled_work(work2.id)
    assert cancelled.status == ScheduledWorkStatus.CANCELLED


def test_scheduled_work_not_found():
    service = ODIService(InMemoryRepository())
    with pytest.raises(ScheduledWorkNotFoundError):
        service.get_scheduled_work("non-existent")


def test_finishing_a_run_writes_exactly_one_briefing():
    service = ODIService(InMemoryRepository())
    work = service.schedule_work(name="Nightly run", schedule_expression="0 0 * * *")

    briefing = service.complete_scheduled_work(
        work.id,
        changes=[RunChange("added", "A new quote mentions onboarding.", "ev-1", "evidence")],
    )

    assert service.get_scheduled_work(work.id).status == ScheduledWorkStatus.COMPLETED
    execution_id = (service.get_scheduled_work(work.id).payload or {}).get("execution_id")
    assert briefing.run_id == execution_id
    assert [item.record_id for item in briefing.items] == ["ev-1"]
    assert service.get_latest_briefing() == briefing
    assert len(service.repo.list_briefings()) == 1


def test_a_second_run_adds_a_second_briefing():
    service = ODIService(InMemoryRepository())
    first = service.schedule_work(name="Night one", schedule_expression="0 0 * * *")
    second = service.schedule_work(name="Night two", schedule_expression="0 0 * * *")

    service.complete_scheduled_work(first.id)
    service.complete_scheduled_work(
        second.id, changes=[RunChange("changed", "O-12 rose to 14.2.", "o-12", "outcome")]
    )

    assert len(service.repo.list_briefings()) == 2
    execution_id = (service.get_scheduled_work(second.id).payload or {}).get("execution_id")
    assert service.get_latest_briefing().run_id == execution_id


def test_a_rerun_of_the_same_run_replaces_its_own_briefing():
    service = ODIService(InMemoryRepository())
    work = service.schedule_work(name="Nightly run", schedule_expression="0 0 * * *")

    service.complete_scheduled_work(work.id)
    service.complete_scheduled_work(
        work.id, changes=[RunChange("added", "A new quote.", "ev-9", "evidence")]
    )

    briefings = service.repo.list_briefings()
    assert len(briefings) == 1
    assert briefings[0].items[0].record_id == "ev-9"


def test_a_run_that_changed_nothing_stores_an_honest_empty_briefing():
    service = ODIService(InMemoryRepository())
    work = service.schedule_work(name="Quiet night", schedule_expression="0 0 * * *")

    briefing = service.complete_scheduled_work(work.id)

    assert briefing.items == ()
    assert not briefing.has_items
    execution_id = (service.get_scheduled_work(work.id).payload or {}).get("execution_id")
    assert service.get_latest_briefing().run_id == execution_id


def test_retries_reuse_the_execution_id_while_new_executions_get_fresh_ids():
    service = ODIService(InMemoryRepository())
    work = service.schedule_work(name="Nightly run", schedule_expression="0 0 * * *")

    first = service.complete_scheduled_work(work.id)
    first_execution_id = first.run_id
    assert first_execution_id == (service.get_scheduled_work(work.id).payload or {}).get(
        "execution_id"
    )

    # A retry of the same execution reuses the id: the briefing is replaced,
    # not duplicated, so only one briefing is stored for that run.
    second = service.complete_scheduled_work(
        work.id, changes=[RunChange("changed", "Retry.", "o-1", "outcome")]
    )
    assert second.run_id == first_execution_id
    assert len(service.repo.list_briefings()) == 1

    # A distinct execution gets a fresh id.
    work2 = service.schedule_work(name="Night two", schedule_expression="0 0 * * *")
    distinct = service.complete_scheduled_work(work2.id)
    assert distinct.run_id != first_execution_id
    assert distinct.run_id == (service.get_scheduled_work(work2.id).payload or {}).get(
        "execution_id"
    )
    assert len(service.repo.list_briefings()) == 2
