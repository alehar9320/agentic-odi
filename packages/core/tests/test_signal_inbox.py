"""Signals: fingerprint dedupe, emissions from real mutations, the attention budget.

A signal must describe something that actually happened, so these tests assert
on the pairing between a write and the one signal it produces — and on the
writes that deliberately produce nothing.
"""

from __future__ import annotations

import hashlib

import pytest
from agentic_odi_core import (
    InMemoryRepository,
    JobStage,
    ODIService,
    SignalBudget,
    SignalKind,
    SignalNotFoundError,
)

STATEMENT = "Minimize the time it takes to deploy a release during an incident"
STAGES = list(JobStage)


def _service(budget: SignalBudget | None = None) -> ODIService:
    return ODIService(InMemoryRepository(), budget=budget)


def _job(service: ODIService) -> str:
    return service.add_job(name="Ship a service", description="Release platform").id


def _kinds(service: ODIService) -> list[str]:
    return [signal.kind.value for signal in service.list_signals(limit=1000)]


def _clear(service: ODIService) -> None:
    for signal in service.list_signals(limit=1000):
        service.dismiss_signal(signal.id)


def test_fingerprint_is_a_sha256_over_the_fact_and_dedupes() -> None:
    service = _service()
    first = service.record_signal(
        SignalKind.EVIDENCE_INGESTED,
        "Evidence arrives",
        subject_kind="evidence",
        subject_id="e-1",
        discriminator="e-1",
    )
    again = service.record_signal(
        SignalKind.EVIDENCE_INGESTED,
        "Evidence arrives",
        subject_kind="evidence",
        subject_id="e-1",
        discriminator="e-1",
    )

    assert again.id == first.id
    assert len(service.list_signals()) == 1
    expected = hashlib.sha256(b"evidence_ingested|evidence|e-1|e-1").hexdigest()
    assert first.fingerprint == expected

    other = service.record_signal(
        SignalKind.EVIDENCE_INGESTED, "Other evidence", subject_kind="evidence", subject_id="e-2"
    )
    assert other.id != first.id
    assert len(service.list_signals()) == 2


def test_adding_a_job_emits_one_job_added_signal() -> None:
    service = _service()
    job_id = _job(service)

    feed = service.list_signals()
    assert [signal.kind for signal in feed] == [SignalKind.JOB_ADDED]
    assert feed[0].subject_kind == "job"
    assert feed[0].subject_id == job_id
    assert feed[0].severity == "info"
    assert "Ship a service" in feed[0].title


def test_creating_an_outcome_is_quiet_and_re_scoring_it_is_not() -> None:
    service = _service()
    job_id = _job(service)
    outcome = service.add_outcome(job_id, STATEMENT, importance=6.0, satisfaction=5.0)
    _clear(service)

    service.update_outcome(outcome.id, {"statement": STATEMENT})
    assert _kinds(service) == []

    service.update_outcome(outcome.id, {"importance": 7.0, "satisfaction": 5.0})
    assert _kinds(service) == ["outcome_scored"]
    scored = service.list_signals()[0]
    assert "7.0" in (scored.detail or "")


def test_crossing_ten_upward_is_urgent_and_downward_is_a_notice() -> None:
    service = _service()
    job_id = _job(service)
    outcome = service.add_outcome(job_id, STATEMENT, importance=6.0, satisfaction=5.0)
    _clear(service)

    service.update_outcome(outcome.id, {"importance": 9.0, "satisfaction": 2.0})
    up = next(s for s in service.list_signals() if s.kind is SignalKind.OPPORTUNITY_CROSSED)
    assert up.severity == "urgent"
    assert "crossed 10 (up)" in up.title
    assert up.detail == "7.0 -> 16.0"

    _clear(service)
    service.update_outcome(outcome.id, {"importance": 6.0, "satisfaction": 6.0})
    down = next(s for s in service.list_signals() if s.kind is SignalKind.OPPORTUNITY_CROSSED)
    assert down.severity == "notice"
    assert "crossed 10 (down)" in down.title

    _clear(service)
    service.update_outcome(outcome.id, {"importance": 5.0, "satisfaction": 5.0})
    assert "opportunity_crossed" not in _kinds(service)


def test_a_score_change_repeats_only_when_the_scores_really_change() -> None:
    service = _service()
    job_id = _job(service)
    outcome = service.add_outcome(job_id, STATEMENT, importance=6.0, satisfaction=5.0)
    _clear(service)

    service.update_outcome(outcome.id, {"importance": 8.0, "satisfaction": 4.0})
    service.update_outcome(outcome.id, {"importance": 8.0, "satisfaction": 4.0})
    assert _kinds(service).count("outcome_scored") == 1


def test_evidence_ingest_and_promotion_each_emit_their_own_signal() -> None:
    service = _service()
    job_id = _job(service)
    evidence = service.add_evidence(
        source_name="gong",
        source_kind="mcp",
        name="customer call",
        content="Deploying during an incident takes hours",
        job_id=job_id,
    )
    _clear(service)

    assert _kinds(service) == []
    service.add_evidence(
        source_name="gong",
        source_kind="mcp",
        name="second call",
        content="Nothing to do with deploys",
        job_id=job_id,
    )
    assert _kinds(service) == ["evidence_ingested"]

    _clear(service)
    outcome = service.promote_evidence(
        evidence.id, "outcome", job_id=job_id, statement=STATEMENT, importance=8.0, satisfaction=3.0
    )
    assert _kinds(service) == ["evidence_promoted"]
    signal = service.list_signals()[0]
    assert signal.subject_kind == "outcome"
    assert signal.subject_id == outcome.id
    assert signal.severity == "notice"


def test_job_map_complete_fires_once_when_all_stages_are_covered() -> None:
    service = _service()
    job_id = _job(service)
    _clear(service)

    for index, stage in enumerate(STAGES[:-1], start=1):
        service.add_step(
            job_id=job_id, name=f"Step {index}", order=index, stage=stage, allow_empty_job_map=True
        )
    assert "job_map_completed" not in _kinds(service)

    final = STAGES[-1]
    service.add_step(
        job_id=job_id,
        name=f"Step {len(STAGES)}",
        order=len(STAGES),
        stage=final,
        allow_empty_job_map=True,
    )
    assert _kinds(service).count("job_map_completed") == 1

    service.add_step(
        job_id=job_id, name="Extra", order=1, stage=JobStage.DEFINE, allow_empty_job_map=True
    )
    assert _kinds(service).count("job_map_completed") == 1


def test_a_stage_edit_can_complete_the_map() -> None:
    service = _service()
    job_id = _job(service)
    for index, stage in enumerate(STAGES[:-1], start=1):
        service.add_step(
            job_id=job_id, name=f"Step {index}", order=index, stage=stage, allow_empty_job_map=True
        )
    loose = service.add_step(
        job_id=job_id, name="Unclassified", order=len(STAGES), allow_empty_job_map=True
    )
    _clear(service)

    service.update_step(loose.id, {"name": "Renamed only"})
    assert "job_map_completed" not in _kinds(service)

    service.update_step(loose.id, {"stage": STAGES[-1]})
    assert _kinds(service) == ["job_map_completed"]


def test_deletions_emit_nothing_but_signals_outlive_their_subject() -> None:
    service = _service()
    job_id = _job(service)
    evidence = service.add_evidence(
        source_name="gong",
        source_kind="mcp",
        name="call",
        content="Deploy pain",
        job_id=job_id,
    )
    assert len(service.list_signals(limit=1000)) == 2

    service.delete_evidence(evidence.id)
    service.delete_job(job_id)

    assert service.repo.get_job(job_id) is None
    assert service.repo.get_evidence(evidence.id) is None
    assert _kinds(service) == ["evidence_ingested", "job_added"]


def test_the_budget_caps_surfaced_signals_and_marks_the_rest_suppressed() -> None:
    service = _service(SignalBudget(daily_cap=2))
    for index in range(5):
        service.record_signal(
            SignalKind.JOB_ADDED,
            f"Job {index}",
            subject_kind="job",
            subject_id=f"j-{index}",
            discriminator=f"j-{index}",
        )

    feed = service.list_signals(limit=1000)
    assert [signal.title for signal in feed] == ["Job 1", "Job 0"]
    assert len(service.repo.signals) == 5
    assert service.count_unread_signals() == 2


def test_urgent_signals_bypass_a_spent_budget() -> None:
    service = _service(SignalBudget(daily_cap=0))
    service.record_signal(SignalKind.JOB_ADDED, "Quiet", subject_kind="job", subject_id="j-1")
    loud = service.record_signal(
        SignalKind.OPPORTUNITY_CROSSED,
        "Crossed",
        subject_kind="outcome",
        subject_id="o-1",
        severity="urgent",
    )

    assert loud.suppressed is False
    assert [signal.suppressed for signal in service.list_signals(limit=1000)] == [False]


def test_a_signal_never_exceeds_the_title_contract() -> None:
    service = _service()
    signal = service.record_signal(SignalKind.JOB_ADDED, "x" * 500, subject_id="j-1")
    assert len(signal.title) == 120


def test_the_budget_reads_the_environment_when_not_given_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENTIC_ODI_SIGNAL_BUDGET", "1")
    service = _service()
    service.record_signal(SignalKind.JOB_ADDED, "One", subject_id="j-1")
    second = service.record_signal(SignalKind.JOB_ADDED, "Two", subject_id="j-2")
    assert second.suppressed is True

    monkeypatch.setenv("AGENTIC_ODI_SIGNAL_BUDGET", "not-a-number")
    assert SignalBudget.from_env().daily_cap == 20


def test_read_and_dismiss_move_the_badge_and_the_feed() -> None:
    service = _service()
    _job(service)
    signal = service.list_signals()[0]

    assert service.count_unread_signals() == 1
    assert [s.id for s in service.list_signals(unread_only=True)] == [signal.id]

    read = service.mark_signal_read(signal.id)
    assert read.read_at is not None
    assert service.count_unread_signals() == 0
    assert service.list_signals(unread_only=True) == []

    dismissed = service.dismiss_signal(signal.id)
    assert dismissed.dismissed_at is not None
    assert service.list_signals() == []


def test_unknown_signal_raises_a_typed_not_found() -> None:
    service = _service()
    for action in (service.mark_signal_read, service.dismiss_signal):
        with pytest.raises(SignalNotFoundError):
            action("nope")


def test_the_feed_is_newest_first_and_honours_the_limit() -> None:
    service = _service()
    for index in range(4):
        service.record_signal(SignalKind.JOB_ADDED, f"Job {index}", subject_id=f"j-{index}")

    feed = service.list_signals(limit=1000)
    assert [signal.title for signal in feed] == ["Job 3", "Job 2", "Job 1", "Job 0"]
    assert [signal.title for signal in service.list_signals(limit=2)] == ["Job 3", "Job 2"]
