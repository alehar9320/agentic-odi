import pytest
from agentic_odi_core import (
    InMemoryRepository,
    ODIService,
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

    # Triggering queues the record for the orchestrator; nothing has run, and
    # the record must not claim a result.
    triggered = service.trigger_scheduled_work(work.id)
    assert triggered.status == ScheduledWorkStatus.SCHEDULED
    assert triggered.trigger_requested_at is not None
    assert triggered.last_run_at is None
    assert "queued for the orchestrator" in (triggered.result_summary or "").lower()
    assert "successfully" not in (triggered.result_summary or "")

    # Cancel task
    work2 = service.schedule_work(name="One-time job", schedule_expression="+1h")
    cancelled = service.cancel_scheduled_work(work2.id)
    assert cancelled.status == ScheduledWorkStatus.CANCELLED


def test_scheduled_work_not_found():
    service = ODIService(InMemoryRepository())
    with pytest.raises(ScheduledWorkNotFoundError):
        service.get_scheduled_work("non-existent")
