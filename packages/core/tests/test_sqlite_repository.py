"""Tests for the SQLite-backed repository and its event-sourced snapshot."""

from __future__ import annotations

import sqlite3

import pytest
from agentic_odi_core.models import (
    BusinessImpactCategory,
    BusinessValue,
    CustomerOutcome,
    CustomerValue,
    Direction,
    Evidence,
    Job,
    Outcome,
    Segment,
    SegmentVerdict,
    Signal,
    SignalKind,
    Step,
    Strategy,
    StrategyKind,
)
from agentic_odi_core.sqlite_repository import SQLiteRepository


def _customer_outcome(job_id: str, *, outcome_id: str = "co-1") -> CustomerOutcome:
    return CustomerOutcome(
        id=outcome_id,
        job_id=job_id,
        customer_value=CustomerValue(
            direction=Direction.MINIMIZE,
            unit_of_measure="minutes",
            object_of_control="time to onboard",
            statement="Minimize the time it takes to onboard",
            importance=8.0,
            satisfaction=4.0,
        ),
        business_value=BusinessValue(
            category=BusinessImpactCategory.REVENUE_GROWTH,
            statement="Increase expansion revenue",
        ),
    )


def test_add_and_read_back_every_entity(tmp_path) -> None:
    repo = SQLiteRepository(str(tmp_path / "odi.db"))
    job = repo.add_job(Job(id="job-1", name="Onboard customers"))
    step = repo.add_step(Step(id="step-1", job_id="job-1", name="Prepare", order=1))
    outcome = repo.add_outcome(
        Outcome(
            id="outcome-1",
            job_id="job-1",
            step_id="step-1",
            statement="Minimize time",
            importance=5.0,
            satisfaction=5.0,
        )
    )
    customer_outcome = repo.add_customer_outcome(_customer_outcome("job-1"))

    assert repo.list_jobs() == [job]
    assert repo.get_job("job-1") == job
    assert repo.get_job("missing") is None
    assert repo.get_steps_for_job("job-1") == [step]
    assert repo.get_outcomes("job-1") == [outcome]
    assert repo.get_outcomes("job-1", step_id="step-1") == [outcome]
    assert repo.get_outcomes("job-1", step_id="other") == []
    assert repo.get_customer_outcome("co-1") == customer_outcome
    assert repo.get_customer_outcome("missing") is None
    assert repo.list_customer_outcomes() == [customer_outcome]
    assert repo.list_customer_outcomes("job-1") == [customer_outcome]
    assert repo.list_customer_outcomes("other") == []


def test_snapshot_reloads_every_event_type_from_disk(tmp_path) -> None:
    db_path = str(tmp_path / "odi.db")
    repo = SQLiteRepository(db_path)
    repo.add_job(Job(id="job-1", name="Onboard customers"))
    repo.add_step(Step(id="step-1", job_id="job-1", name="Prepare", order=1))
    repo.add_outcome(
        Outcome(
            id="outcome-1",
            job_id="job-1",
            statement="Minimize time",
            importance=5.0,
            satisfaction=5.0,
        )
    )
    created = repo.add_customer_outcome(_customer_outcome("job-1"))
    customer_value = created.customer_value.model_dump()
    customer_value["importance"] = 9.0
    repo.update_customer_outcome("co-1", {"customer_value": customer_value})

    reloaded = SQLiteRepository(db_path)

    assert reloaded.get_job("job-1") is not None
    assert reloaded.get_steps_for_job("job-1")[0].name == "Prepare"
    assert reloaded.get_outcomes("job-1")[0].statement == "Minimize time"
    reloaded_outcome = reloaded.get_customer_outcome("co-1")
    assert reloaded_outcome is not None
    assert reloaded_outcome.customer_value.importance == 9.0


def test_snapshot_drops_customer_outcomes_after_delete_event(tmp_path) -> None:
    db_path = str(tmp_path / "odi.db")
    repo = SQLiteRepository(db_path)
    repo.add_customer_outcome(_customer_outcome("job-1"))
    assert repo.delete_customer_outcome("co-1") is True

    reloaded = SQLiteRepository(db_path)

    assert reloaded.get_customer_outcome("co-1") is None


def test_snapshot_skips_invalid_update_events(tmp_path) -> None:
    db_path = str(tmp_path / "odi.db")
    repo = SQLiteRepository(db_path)
    repo.add_customer_outcome(_customer_outcome("job-1"))
    repo.store.append(
        "CUSTOMER_OUTCOME_UPDATED",
        {"id": "co-1", "updates": {"customer_value": {"importance": 99.0}}},
    )

    reloaded = SQLiteRepository(db_path)

    reloaded_outcome = reloaded.get_customer_outcome("co-1")
    assert reloaded_outcome is not None
    assert reloaded_outcome.customer_value.importance == 8.0


def test_update_customer_outcome_returns_none_for_missing_or_invalid(tmp_path) -> None:
    repo = SQLiteRepository(str(tmp_path / "odi.db"))

    assert repo.update_customer_outcome("missing", {}) is None

    repo.add_customer_outcome(_customer_outcome("job-1"))
    assert repo.update_customer_outcome("co-1", {"customer_value": {"importance": 99.0}}) is None


def test_delete_customer_outcome_reports_missing_id(tmp_path) -> None:
    repo = SQLiteRepository(str(tmp_path / "odi.db"))

    assert repo.delete_customer_outcome("missing") is False


def test_clear_removes_all_entities_and_events(tmp_path) -> None:
    repo = SQLiteRepository(str(tmp_path / "odi.db"))
    repo.add_job(Job(id="job-1", name="Onboard customers"))
    repo.add_customer_outcome(_customer_outcome("job-1"))

    repo.clear()

    assert repo.list_jobs() == []
    assert repo.list_customer_outcomes() == []
    assert repo.store.get_stream() == []


def test_default_path_uses_environment_override(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "nested" / "odi.db"
    monkeypatch.setenv("AGENTIC_ODI_DB", str(db_path))

    repo = SQLiteRepository()

    assert db_path.exists()
    assert repo.list_jobs() == []


def test_snapshot_ignores_unknown_event_types(tmp_path) -> None:
    db_path = str(tmp_path / "odi.db")
    repo = SQLiteRepository(db_path)
    repo.store.append("SOMETHING_ELSE", {"id": "x"})

    reloaded = SQLiteRepository(db_path)

    assert reloaded.list_jobs() == []


def test_closing_the_store_prevents_further_reads(tmp_path) -> None:
    repo = SQLiteRepository(str(tmp_path / "odi.db"))
    repo.store.close()

    with pytest.raises(sqlite3.ProgrammingError):
        repo.store.get_stream()


def _linked_customer_outcome(id: str, job_id: str, step_id: str | None = None) -> CustomerOutcome:
    return CustomerOutcome(
        id=id,
        job_id=job_id,
        step_id=step_id,
        customer_value=CustomerValue(
            direction=Direction.MINIMIZE,
            unit_of_measure="minutes",
            object_of_control="support team",
            statement="Minimize resolution time",
            importance=9.0,
            satisfaction=3.0,
        ),
        business_value=BusinessValue(
            category=BusinessImpactCategory.COST_REDUCTION,
            statement="Reduce support cost",
        ),
    )


def test_round_trips_all_entity_types(tmp_path):
    db = str(tmp_path / "odi.db")
    repo = SQLiteRepository(db_path=db)
    repo.add_job(Job(id="j1", name="Job", description="d"))
    repo.add_step(Step(id="s1", job_id="j1", name="Step", order=1))
    repo.add_outcome(
        Outcome(
            id="o1",
            job_id="j1",
            step_id="s1",
            statement="Min x",
            importance=8.0,
            satisfaction=4.0,
            opportunity_score=12.0,
        )
    )

    reopened = SQLiteRepository(db_path=db)
    assert reopened.get_job("j1").name == "Job"  # type: ignore[union-attr]
    assert reopened.get_step("s1").order == 1  # type: ignore[union-attr]
    assert reopened.get_outcome("o1").opportunity_score == 12.0  # type: ignore[union-attr]


def test_concurrent_writer_is_visible(tmp_path):
    db = str(tmp_path / "odi.db")
    reader = SQLiteRepository(db_path=db)
    writer = SQLiteRepository(db_path=db)
    writer.add_job(Job(id="j1", name="Job"))
    assert reader.get_job("j1") is not None  # read-through sees the other connection's write


def test_delete_job_cascades_after_reopen(tmp_path):
    db = str(tmp_path / "odi.db")
    repo = SQLiteRepository(db_path=db)
    repo.add_job(Job(id="j1", name="Job"))
    repo.add_step(Step(id="s1", job_id="j1", name="Step", order=1))
    repo.add_outcome(
        Outcome(
            id="o1", job_id="j1", step_id="s1", statement="Min x", importance=5.0, satisfaction=5.0
        )
    )
    repo.delete_job("j1")

    reopened = SQLiteRepository(db_path=db)
    assert reopened.get_job("j1") is None
    assert reopened.get_step("s1") is None
    assert reopened.get_outcome("o1") is None


def test_update_outcome_persists(tmp_path):
    db = str(tmp_path / "odi.db")
    repo = SQLiteRepository(db_path=db)
    repo.add_outcome(
        Outcome(id="o1", job_id="j1", statement="Min x", importance=5.0, satisfaction=5.0)
    )
    repo.update_outcome("o1", {"statement": "Max y", "opportunity_score": 5.0})
    assert SQLiteRepository(db_path=db).get_outcome("o1").statement == "Max y"  # type: ignore[union-attr]


def test_update_job_and_step_merge_or_return_none_when_missing(tmp_path):
    db = str(tmp_path / "odi.db")
    repo = SQLiteRepository(db_path=db)
    repo.add_job(Job(id="j1", name="Job"))
    repo.add_step(Step(id="s1", job_id="j1", name="Step", order=1))

    updated_job = repo.update_job("j1", {"name": "Renamed"})
    assert updated_job is not None and updated_job.name == "Renamed"
    updated_step = repo.update_step("s1", {"name": "Renamed step"})
    assert updated_step is not None and updated_step.name == "Renamed step"
    assert repo.update_job("nope", {"name": "x"}) is None
    assert repo.update_step("nope", {"name": "x"}) is None

    reopened = SQLiteRepository(db_path=db)
    assert reopened.get_job("j1").name == "Renamed"  # type: ignore[union-attr]
    assert reopened.get_step("s1").name == "Renamed step"  # type: ignore[union-attr]


def test_delete_missing_returns_false_and_cascade_events_replay(tmp_path):
    db = str(tmp_path / "odi.db")
    repo = SQLiteRepository(db_path=db)
    assert repo.delete_job("nope") is False
    assert repo.delete_step("nope") is False
    assert repo.delete_outcome("nope") is False

    repo.add_job(Job(id="j1", name="Job"))
    repo.add_step(Step(id="s1", job_id="j1", name="Step", order=1))
    repo.add_outcome(
        Outcome(
            id="o1", job_id="j1", step_id="s1", statement="Min x", importance=5.0, satisfaction=5.0
        )
    )
    repo.add_outcome(
        Outcome(id="o2", job_id="j1", statement="Unbound", importance=5.0, satisfaction=5.0)
    )
    assert repo.delete_step("s1") is True
    assert repo.delete_outcome("o2") is True
    assert repo.delete_job("j1") is True
    assert repo.delete_job("j1") is False

    reopened = SQLiteRepository(db_path=db)
    assert reopened.get_step("s1") is None
    assert reopened.get_outcome("o1") is None
    assert reopened.get_outcome("o2") is None
    assert reopened.get_job("j1") is None


def test_read_through_sees_update_and_delete_from_other_connection(tmp_path):
    db = str(tmp_path / "odi.db")
    reader = SQLiteRepository(db_path=db)
    writer = SQLiteRepository(db_path=db)
    writer.add_job(Job(id="j1", name="Job"))
    assert reader.get_job("j1").name == "Job"  # type: ignore[union-attr]

    writer.update_job("j1", {"name": "Renamed"})
    assert reader.get_job("j1").name == "Renamed"  # type: ignore[union-attr]

    writer.delete_job("j1")
    assert reader.get_job("j1") is None
    assert reader.list_jobs() == []


def test_customer_outcome_update_and_delete_persist(tmp_path):
    db = str(tmp_path / "odi.db")
    repo = SQLiteRepository(db_path=db)
    repo.add_customer_outcome(_linked_customer_outcome("co1", job_id="j1"))
    updated = repo.update_customer_outcome("co1", {"job_id": "j2"})
    assert updated is not None and updated.job_id == "j2"
    assert repo.update_customer_outcome("nope", {"job_id": "x"}) is None

    other = SQLiteRepository(db_path=db)
    assert other.get_customer_outcome("co1").job_id == "j2"  # type: ignore[union-attr]
    assert other.delete_customer_outcome("co1") is True
    assert other.delete_customer_outcome("co1") is False

    reopened = SQLiteRepository(db_path=db)
    assert reopened.get_customer_outcome("co1") is None


def test_delete_job_cascades_customer_outcomes_after_reopen(tmp_path):
    db = str(tmp_path / "odi.db")
    repo = SQLiteRepository(db_path=db)
    repo.add_job(Job(id="j1", name="Job"))
    repo.add_step(Step(id="s1", job_id="j1", name="Step", order=1))
    repo.add_customer_outcome(_linked_customer_outcome("co1", job_id="j1", step_id="s1"))
    repo.add_customer_outcome(_linked_customer_outcome("co2", job_id="other"))
    assert repo.delete_job("j1") is True

    reopened = SQLiteRepository(db_path=db)
    assert reopened.get_customer_outcome("co1") is None
    assert reopened.get_customer_outcome("co2") is not None


def _evidence(id: str, **overrides) -> Evidence:
    payload = {
        "id": id,
        "source_name": "gong",
        "source_kind": "mcp",
        "item_type": "resource",
        "name": "feedback",
        "content": "Lost hours on deploy",
    }
    payload.update(overrides)
    return Evidence(**payload)


def test_evidence_round_trips_and_filters(tmp_path):
    db = str(tmp_path / "odi.db")
    repo = SQLiteRepository(db_path=db)
    repo.add_evidence(_evidence("e1", job_id="j1", step_id="s1", outcome_id="o1"))
    repo.add_evidence(_evidence("e2", job_id="j1"))

    reopened = SQLiteRepository(db_path=db)
    assert reopened.get_evidence("e1").name == "feedback"  # type: ignore[union-attr]
    assert len(reopened.list_evidence(job_id="j1")) == 2
    assert [item.id for item in reopened.list_evidence(step_id="s1")] == ["e1"]
    assert [item.id for item in reopened.list_evidence(outcome_id="o1")] == ["e1"]
    assert reopened.delete_evidence("e1") is True
    assert reopened.delete_evidence("e1") is False
    assert SQLiteRepository(db_path=db).get_evidence("e1") is None


def test_delete_job_cascades_evidence_after_reopen(tmp_path):
    db = str(tmp_path / "odi.db")
    repo = SQLiteRepository(db_path=db)
    repo.add_job(Job(id="j1", name="Job"))
    repo.add_evidence(_evidence("e1", job_id="j1"))
    repo.add_evidence(_evidence("e2", job_id="other"))

    assert repo.delete_job("j1") is True

    reopened = SQLiteRepository(db_path=db)
    assert reopened.get_evidence("e1") is None
    assert reopened.get_evidence("e2") is not None


def test_clear_removes_everything(tmp_path):
    db = str(tmp_path / "odi.db")
    repo = SQLiteRepository(db_path=db)
    repo.add_job(Job(id="j1", name="Job"))
    repo.clear()

    assert repo.get_job("j1") is None
    assert SQLiteRepository(db_path=db).get_job("j1") is None


def test_the_connection_is_configured_for_concurrent_writers(tmp_path):
    from agentic_odi_core.intent_store import IntentStore

    store = IntentStore(str(tmp_path / "events.db"))
    try:
        assert store.conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        assert store.conn.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
    finally:
        store.close()


def test_concurrent_writers_both_land_even_when_the_lock_is_contended(tmp_path):
    import threading

    db = str(tmp_path / "odi.db")
    writers = [SQLiteRepository(db_path=db) for _ in range(6)]
    failures: list[BaseException] = []
    start = threading.Barrier(len(writers))

    def write(repo: SQLiteRepository, index: int) -> None:
        try:
            start.wait()
            for attempt in range(10):
                repo.add_job(Job(id=f"j{index}-{attempt}", name=f"Job {index}-{attempt}"))
        except BaseException as error:  # noqa: BLE001 - the assertion reports it
            failures.append(error)

    threads = [
        threading.Thread(target=write, args=(repo, index)) for index, repo in enumerate(writers)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert failures == []
    reopened = SQLiteRepository(db_path=db)
    assert len(reopened.list_jobs()) == 60


def test_reload_keeps_the_snapshot_on_disk(tmp_path) -> None:
    repo = SQLiteRepository(str(tmp_path / "odi.db"))
    repo.add_job(Job(id="job-1", name="Job", description=""))

    repo.reload()

    assert [job.id for job in repo.list_jobs()] == ["job-1"]


def test_get_outcomes_ranks_by_opportunity_score(tmp_path) -> None:
    from agentic_odi_core.models import Job, Outcome

    repo = SQLiteRepository(str(tmp_path / "odi.db"))
    repo.add_job(Job(id="job-1", name="Onboard customers"))
    repo.add_outcome(Outcome(id="o-low", job_id="job-1", statement="low", opportunity_score=4.0))
    repo.add_outcome(Outcome(id="o-high", job_id="job-1", statement="high", opportunity_score=15.0))
    repo.add_outcome(Outcome(id="o-none", job_id="job-1", statement="unscored"))

    assert [o.id for o in repo.get_outcomes("job-1")] == ["o-high", "o-low", "o-none"]
    assert [o.id for o in repo.get_outcomes("job-1", sort="insertion")] == [
        "o-low",
        "o-high",
        "o-none",
    ]


def test_close_leaves_no_wal_or_shm_sidecars(tmp_path) -> None:
    db_path = tmp_path / "odi.db"
    repo = SQLiteRepository(str(db_path))
    repo.add_job(Job(id="job-1", name="Onboard customers"))
    assert (tmp_path / "odi.db-wal").exists()

    repo.close()

    assert db_path.exists()
    assert list(tmp_path.glob("odi.db-wal")) == []
    assert list(tmp_path.glob("odi.db-shm")) == []


def test_signals_survive_a_reload_from_the_event_log(tmp_path) -> None:
    db = str(tmp_path / "odi.db")
    repo = SQLiteRepository(db_path=db)
    quiet = Signal(
        id="sig-1",
        kind=SignalKind.JOB_ADDED,
        title='Job added: "Onboard"',
        subject_kind="job",
        subject_id="job-1",
        suppressed=True,
        fingerprint="fp-1",
    )
    loud = Signal(
        id="sig-2",
        kind=SignalKind.OPPORTUNITY_CROSSED,
        title="Opportunity score crossed 10 (up)",
        subject_kind="outcome",
        subject_id="o-1",
        severity="urgent",
        fingerprint="fp-2",
    )
    fresh = Signal(
        id="sig-3",
        kind=SignalKind.EVIDENCE_INGESTED,
        title='Evidence from "gong": call',
        subject_kind="evidence",
        subject_id="e-1",
        fingerprint="fp-3",
    )
    repo.add_signal(quiet)
    repo.add_signal(loud)
    repo.add_signal(fresh)

    assert repo.mark_signal_read("sig-2") is not None

    reopened = SQLiteRepository(db_path=db)
    restored_quiet = reopened.get_signal("sig-1")
    restored_loud = reopened.get_signal("sig-2")
    assert restored_quiet is not None and restored_loud is not None
    assert restored_quiet.created_at == quiet.created_at
    assert restored_quiet.suppressed is True
    assert restored_loud.severity == "urgent"
    assert restored_loud.read_at is not None

    assert [signal.id for signal in reopened.list_signals()] == ["sig-3", "sig-2"]
    assert [signal.id for signal in reopened.list_signals(unread_only=True)] == ["sig-3"]
    assert reopened.count_unread_signals() == 1

    assert reopened.dismiss_signal("sig-3") is not None
    assert reopened.count_unread_signals() == 0

    assert reopened.mark_signal_read("missing") is None
    assert reopened.dismiss_signal("missing") is None


def _segment(id: str = "seg-1", confidence: float = 0.75) -> Segment:
    return Segment(
        id=id,
        job_id="job-1",
        name="Platform engineers, gather the current values",
        people="Platform engineers",
        job_statement="Rotate a leaked secret without an outage",
        outcome_ids=["o-1", "o-2"],
        verdict=SegmentVerdict.UNDERSERVED,
        rationale="2 outcomes on the gather step.",
        confidence=confidence,
    )


def _strategy() -> Strategy:
    return Strategy(
        id="st-1",
        kind=StrategyKind.DIFFERENTIATED,
        segment_id="seg-1",
        thesis="Improve the existing product against the gap.",
        bets=["Build against o-1"],
        rejected=[{"kind": "disruptive", "why": "nobody is overserved"}],
    )


def test_segments_and_strategies_survive_a_reload_from_the_event_log(tmp_path) -> None:
    db = str(tmp_path / "odi.db")
    repo = SQLiteRepository(db_path=db)
    repo.add_job(Job(id="job-1", name="Rotate a leaked secret"))
    repo.add_segment(_segment())
    repo.add_strategy(_strategy())

    assert repo.update_segment("seg-1", {"confidence": 0.9}) is not None
    assert repo.update_strategy("st-1", {"thesis": "Revised after the interview."}) is not None

    reopened = SQLiteRepository(db_path=db)
    restored_segment = reopened.get_segment("seg-1")
    restored_strategy = reopened.get_strategy("st-1")
    assert restored_segment is not None and restored_strategy is not None
    assert restored_segment.confidence == 0.9
    assert restored_segment.outcome_ids == ["o-1", "o-2"]
    assert restored_segment.verdict is SegmentVerdict.UNDERSERVED
    assert restored_strategy.thesis == "Revised after the interview."
    assert restored_strategy.rejected == [{"kind": "disruptive", "why": "nobody is overserved"}]
    assert [segment.id for segment in reopened.list_segments()] == ["seg-1"]
    assert reopened.list_segments(job_id="job-2") == []
    assert [strategy.id for strategy in reopened.list_strategies()] == ["st-1"]
    assert reopened.list_strategies(segment_id="other") == []


def test_segments_and_strategies_are_recorded_as_events(tmp_path) -> None:
    db = str(tmp_path / "odi.db")
    repo = SQLiteRepository(db_path=db)
    repo.add_job(Job(id="job-1", name="Rotate a leaked secret"))
    repo.add_segment(_segment())
    repo.add_strategy(_strategy())
    repo.update_segment("seg-1", {"confidence": 0.9})

    assert [event["type"] for event in repo.store.get_stream()] == [
        "JOB_CREATED",
        "SEGMENT_CREATED",
        "STRATEGY_CREATED",
        "SEGMENT_UPDATED",
    ]


def test_a_segment_update_for_an_unknown_id_is_not_recorded(tmp_path) -> None:
    db = str(tmp_path / "odi.db")
    repo = SQLiteRepository(db_path=db)

    assert repo.update_segment("missing", {"confidence": 0.5}) is None
    assert repo.update_strategy("missing", {"thesis": "Nothing"}) is None
    assert repo.get_segment("missing") is None
    assert repo.get_strategy("missing") is None
