"""Stages become data (A7 / ALH-20).

The eight Universal Job Map stages are a fixed sequence, so ``order`` and
``stage`` are two names for the same position and must agree. A step written
before ``stage`` existed is given the stage its order names by a recorded
``STEP_STAGE_BACKFILLED`` event, once, so the migration is visible in the log
and replay reproduces the same values. A step whose order is outside 1–8
acquires no invented stage.
"""

from __future__ import annotations

import pytest
from agentic_odi_core import InMemoryRepository, ODIService
from agentic_odi_core.models import JOB_STAGE_INDEX, JOB_STAGE_ORDER, JobStage, Step
from agentic_odi_core.sqlite_repository import SQLiteRepository

VALID = "Minimize the time it takes to onboard a customer when they sign up"


@pytest.fixture
def service() -> ODIService:
    return ODIService(InMemoryRepository())


def _job_with_one_outcome(service: ODIService) -> str:
    job = service.add_job("Onboard customers")
    service.add_outcome(job.id, VALID, importance=8.0, satisfaction=4.0)
    return job.id


def test_order_and_stage_agree_across_all_eight_positions(service: ODIService) -> None:
    job_id = _job_with_one_outcome(service)

    for order, stage in enumerate(JOB_STAGE_ORDER, start=1):
        step = service.add_step(job_id, stage.value, order=order, stage=stage)
        assert step.order == order
        assert step.stage is stage
        assert step.stage_index == order


def test_order_three_with_stage_prepare_succeeds(service: ODIService) -> None:
    job_id = _job_with_one_outcome(service)

    step = service.add_step(job_id, "Prepare", order=3, stage=JobStage.PREPARE)

    assert step.stage is JobStage.PREPARE
    assert step.stage_index == 3


def test_order_three_with_stage_conclude_is_rejected_naming_both(
    service: ODIService,
) -> None:
    job_id = _job_with_one_outcome(service)

    with pytest.raises(ValueError) as excinfo:
        service.add_step(job_id, "Mismatch", order=3, stage=JobStage.CONCLUDE)

    message = str(excinfo.value)
    assert "order=3" in message
    assert "conclude" in message
    assert "prepare" in message, "the message must name the stage the order implies"


def test_a_step_without_a_stage_is_left_alone(service: ODIService) -> None:
    # No stage is not a claim about the stage, so there is nothing to disagree.
    job_id = _job_with_one_outcome(service)

    step = service.add_step(job_id, "Unlabelled", order=3)

    assert step.stage is None
    assert step.stage_index is None


def test_updating_order_without_moving_the_stage_is_rejected(
    service: ODIService,
) -> None:
    job_id = _job_with_one_outcome(service)
    step = service.add_step(job_id, "Prepare", order=3, stage=JobStage.PREPARE)

    with pytest.raises(ValueError) as excinfo:
        service.update_step(step.id, {"order": 5})

    message = str(excinfo.value)
    assert "order=5" in message
    assert "prepare" in message


def test_updating_order_and_stage_together_succeeds(service: ODIService) -> None:
    job_id = _job_with_one_outcome(service)
    step = service.add_step(job_id, "Prepare", order=3, stage=JobStage.PREPARE)

    updated = service.update_step(step.id, {"order": 5, "stage": JobStage.EXECUTE})

    assert updated.order == 5
    assert updated.stage is JobStage.EXECUTE
    assert updated.stage_index == 5


def test_the_schema_exposes_the_stage_enum() -> None:
    from agentic_odi_core.schema import odi_schema

    schema = odi_schema()
    stage = schema["Step"]["properties"]["stage"]

    assert "JobStage" in str(stage), "the Step schema must reference the JobStage enum"
    enum = schema["Step"]["$defs"]["JobStage"]["enum"]
    assert enum == [stage.value for stage in JOB_STAGE_ORDER]


def test_the_canonical_order_is_one_through_eight() -> None:
    assert [JOB_STAGE_INDEX[stage] for stage in JOB_STAGE_ORDER] == list(range(1, 9))


def test_legacy_steps_are_backfilled_by_an_event_not_an_in_place_edit(tmp_path) -> None:
    db = str(tmp_path / "odi.db")
    repo = SQLiteRepository(db)
    # A step as an older writer would have stored it: order, no stage.
    repo.add_step(Step(id="step-3", job_id="job-1", name="Prepare", order=3))

    # Reopening runs the backfill.
    reopened = SQLiteRepository(db)
    step = reopened.get_step("step-3")
    assert step is not None
    assert step.stage is JobStage.PREPARE
    assert step.stage_index == 3

    events = [ev for ev in reopened.store.get_stream() if ev["type"] == "STEP_STAGE_BACKFILLED"]
    assert len(events) == 1, "the backfill must be recorded as an event"


def test_the_backfill_runs_only_on_the_first_open(tmp_path) -> None:
    db = str(tmp_path / "odi.db")
    repo = SQLiteRepository(db)
    repo.add_step(Step(id="step-3", job_id="job-1", name="Prepare", order=3))

    first = SQLiteRepository(db)
    before = len([ev for ev in first.store.get_stream() if ev["type"] == "STEP_STAGE_BACKFILLED"])
    second = SQLiteRepository(db)
    after = len([ev for ev in second.store.get_stream() if ev["type"] == "STEP_STAGE_BACKFILLED"])

    assert before == after == 1, "a second open must not re-backfill"


def test_the_backfilled_stage_survives_replay(tmp_path) -> None:
    db = str(tmp_path / "odi.db")
    repo = SQLiteRepository(db)
    repo.add_step(Step(id="step-3", job_id="job-1", name="Prepare", order=3))

    reopened = SQLiteRepository(db)
    live = reopened.get_step("step-3")
    reopened.reload()
    assert reopened.get_step("step-3") == live


def test_a_step_outside_one_to_eight_acquires_no_invented_stage(tmp_path) -> None:
    db = str(tmp_path / "odi.db")
    repo = SQLiteRepository(db)
    repo.add_step(Step(id="step-9", job_id="job-1", name="Off-map", order=9))

    reopened = SQLiteRepository(db)
    step = reopened.get_step("step-9")

    assert step is not None
    assert step.stage is None, "there is no honest stage for an order outside 1-8"
    events = [ev for ev in reopened.store.get_stream() if ev["type"] == "STEP_STAGE_BACKFILLED"]
    assert events == [], "no invented stage means no backfill event"
