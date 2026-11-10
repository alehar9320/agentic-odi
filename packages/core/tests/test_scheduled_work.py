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


def _fixed_now():
    from datetime import datetime, timezone

    return datetime(2026, 5, 1, 2, 0, 0, tzinfo=timezone.utc)


def test_run_records_success_and_resets_attempts():
    service = ODIService(InMemoryRepository())
    work = service.schedule_work(name="Morning brief", schedule_expression="0 2 * * *")

    def runner(_work):
        return "ok"

    ran = service.run_scheduled_work(work.id, runner, now=_fixed_now())

    assert ran.last_status == "ok"
    assert ran.attempts == 0
    assert ran.last_error is None
    assert ran.next_run_at is None
    assert ran.status == ScheduledWorkStatus.COMPLETED
    assert ran.last_run_at == _fixed_now().isoformat()


def test_failed_run_is_not_recorded_as_completed():
    service = ODIService(InMemoryRepository())
    work = service.schedule_work(name="Morning brief", schedule_expression="0 2 * * *")

    def runner(_work):
        raise RuntimeError("model unreachable")

    failed = service.run_scheduled_work(work.id, runner, now=_fixed_now())

    assert failed.last_status == "failed"
    assert failed.status != ScheduledWorkStatus.COMPLETED
    assert failed.attempts == 1
    assert failed.last_error == "RuntimeError: model unreachable"
    # First failure waits two minutes: 02:02 on the same day.
    assert failed.next_run_at == "2026-05-01T02:02:00+00:00"
    assert "retrying at 2026-05-01T02:02:00+00:00" in (failed.result_summary or "")
    assert "attempt 1 of 3" in (failed.result_summary or "")


def test_third_failure_stops_the_schedule():
    service = ODIService(InMemoryRepository())
    work = service.schedule_work(name="Morning brief", schedule_expression="0 2 * * *")

    def runner(_work):
        raise ValueError("boom")

    first = service.run_scheduled_work(work.id, runner, now=_fixed_now())
    assert first.attempts == 1
    assert first.next_run_at is not None

    second = service.run_scheduled_work(work.id, runner, now=_fixed_now())
    assert second.attempts == 2
    assert second.next_run_at == "2026-05-01T02:04:00+00:00"

    third = service.run_scheduled_work(work.id, runner, now=_fixed_now())
    assert third.attempts == 3
    assert third.next_run_at is None
    assert third.status == ScheduledWorkStatus.FAILED
    assert "needs attention" in (third.result_summary or "")

    # The fourth run is not scheduled, but the item is still listable.
    assert service.list_scheduled_work()[0].id == work.id


def test_retry_delay_is_capped():
    from agentic_odi_core.schedule import retry_delay_minutes

    assert retry_delay_minutes(1) == 2
    assert retry_delay_minutes(2) == 4
    assert retry_delay_minutes(10) == 30


def test_success_after_failures_resets_the_counter():
    service = ODIService(InMemoryRepository())
    work = service.schedule_work(name="Morning brief", schedule_expression="0 2 * * *")

    def failing(_work):
        raise RuntimeError("flaky")

    service.run_scheduled_work(work.id, failing, now=_fixed_now())
    service.run_scheduled_work(work.id, failing, now=_fixed_now())
    recovered = service.run_scheduled_work(work.id, lambda _w: "ok", now=_fixed_now())

    assert recovered.last_status == "ok"
    assert recovered.attempts == 0
    assert recovered.last_error is None
    assert recovered.next_run_at is None


def test_scheduled_work_fields_round_trip_through_sqlite(tmp_path):
    from agentic_odi_core.sqlite_repository import SQLiteRepository

    db_path = str(tmp_path / "odi.db")
    repo = SQLiteRepository(db_path)
    service = ODIService(repo)
    work = service.schedule_work(name="Morning brief", schedule_expression="0 2 * * *")

    def failing(_work):
        raise RuntimeError("model unreachable")

    service.run_scheduled_work(work.id, failing, now=_fixed_now())

    # A fresh repository reads the same row back with the failure intact.
    reloaded = SQLiteRepository(db_path)
    stored = reloaded.get_scheduled_work(work.id)
    assert stored is not None
    assert stored.last_status == "failed"
    assert stored.attempts == 1
    assert stored.last_error == "RuntimeError: model unreachable"
    assert stored.next_run_at == "2026-05-01T02:02:00+00:00"

    # A row created before the change deserializes with the additive defaults.
    untouched = reloaded.add_scheduled_work(
        ScheduledWork(name="Old row", schedule_expression="+1h")
    )
    assert untouched.last_status is None
    assert untouched.attempts == 0
    assert untouched.last_error is None
