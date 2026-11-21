"""Tests for the in-memory Repository implementation."""

from __future__ import annotations

import uuid

import pytest
from agentic_odi_core.errors import ConflictError
from agentic_odi_core.models import (
    BusinessImpactCategory,
    BusinessValue,
    CandidateSolution,
    CandidateStatus,
    CustomerOutcome,
    CustomerValue,
    Direction,
    Evidence,
    Job,
    Link,
    Outcome,
    RelationshipType,
    Signal,
    SignalKind,
    Step,
    StrategyKind,
)
from agentic_odi_core.repository import InMemoryRepository, rank_outcomes


def _link(
    link_id: str | None = None,
    *,
    source_type: str = "evidence",
    source_id: str = "evidence-1",
    target_type: str = "outcome",
    target_id: str = "outcome-1",
    relationship: RelationshipType = RelationshipType.EVIDENCE_FOR,
) -> Link:
    return Link(
        id=link_id or str(uuid.uuid4()),
        source_type=source_type,
        source_id=source_id,
        target_type=target_type,
        target_id=target_id,
        relationship_type=relationship,
    )


def _customer_outcome(outcome_id: str, job_id: str = "job-1") -> CustomerOutcome:
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
            category=BusinessImpactCategory.COST_REDUCTION,
            statement="Reduce support cost",
        ),
    )


def test_get_outcomes_filters_by_step() -> None:
    repo = InMemoryRepository()
    repo.add_outcome(
        Outcome(
            id="o-1",
            job_id="job-1",
            step_id="step-1",
            statement="one",
            importance=5.0,
            satisfaction=5.0,
        )
    )
    repo.add_outcome(
        Outcome(
            id="o-2",
            job_id="job-1",
            step_id="step-2",
            statement="two",
            importance=5.0,
            satisfaction=5.0,
        )
    )

    assert [o.id for o in repo.get_outcomes("job-1", step_id="step-1")] == ["o-1"]
    assert [o.id for o in repo.get_outcomes("job-1")] == ["o-1", "o-2"]


def test_list_customer_outcomes_without_filter_returns_all() -> None:
    repo = InMemoryRepository()
    repo.add_customer_outcome(_customer_outcome("co-1", "job-1"))
    repo.add_customer_outcome(_customer_outcome("co-2", "job-2"))

    assert [co.id for co in repo.list_customer_outcomes()] == ["co-1", "co-2"]
    assert [co.id for co in repo.list_customer_outcomes("job-2")] == ["co-2"]


def test_update_customer_outcome_returns_none_for_missing_id() -> None:
    assert InMemoryRepository().update_customer_outcome("missing", {}) is None


def test_update_customer_outcome_rejects_invalid_updates() -> None:
    repo = InMemoryRepository()
    repo.add_customer_outcome(_customer_outcome("co-1"))

    with pytest.raises(ValueError):
        repo.update_customer_outcome("co-1", {"customer_value": {"importance": 99.0}})


def test_delete_customer_outcome_reports_missing_id() -> None:
    assert InMemoryRepository().delete_customer_outcome("missing") is False


def test_clear_removes_all_entities() -> None:
    repo = InMemoryRepository()
    job = repo.add_job(Job(id="job-1", name="Onboard customers"))
    repo.add_step(Step(id="step-1", job_id=job.id, name="Prepare", order=1))
    repo.add_outcome(
        Outcome(
            id="o-1", job_id=job.id, statement="Minimize time", importance=5.0, satisfaction=5.0
        )
    )
    repo.add_customer_outcome(_customer_outcome("co-1", job.id))

    repo.clear()

    assert repo.list_jobs() == []
    assert repo.get_steps_for_job(job.id) == []
    assert repo.get_outcomes(job.id) == []
    assert repo.list_customer_outcomes() == []


def _repo_with_graph() -> InMemoryRepository:
    repo = InMemoryRepository()
    repo.add_job(Job(id="j1", name="Job"))
    repo.add_step(Step(id="s1", job_id="j1", name="Step", order=1))
    repo.add_outcome(
        Outcome(
            id="o1", job_id="j1", step_id="s1", statement="Min x", importance=5.0, satisfaction=5.0
        )
    )
    return repo


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


def test_get_step_and_get_outcome():
    repo = _repo_with_graph()
    assert repo.get_step("s1").name == "Step"  # type: ignore[union-attr]
    assert repo.get_outcome("o1").statement == "Min x"  # type: ignore[union-attr]
    assert repo.get_step("missing") is None


def test_update_job_merges_and_returns_none_when_missing():
    repo = _repo_with_graph()
    updated = repo.update_job("j1", {"name": "Renamed"})
    assert updated is not None and updated.name == "Renamed"
    assert repo.update_job("nope", {"name": "x"}) is None


def test_delete_job_cascades_dependents():
    repo = _repo_with_graph()
    assert repo.delete_job("j1") is True
    assert repo.get_job("j1") is None
    assert repo.get_step("s1") is None
    assert repo.get_outcome("o1") is None
    assert repo.delete_job("j1") is False


def test_delete_step_cascades_its_outcomes():
    repo = _repo_with_graph()
    repo.add_outcome(
        Outcome(id="o2", job_id="j1", statement="Unbound", importance=5.0, satisfaction=5.0)
    )
    assert repo.delete_step("s1") is True
    assert repo.get_step("s1") is None
    assert repo.get_outcome("o1") is None
    assert repo.get_outcome("o2") is not None


def test_update_step_and_update_outcome_merge_or_return_none():
    repo = _repo_with_graph()
    updated_step = repo.update_step("s1", {"name": "Renamed step"})
    assert updated_step is not None and updated_step.name == "Renamed step"
    updated_outcome = repo.update_outcome("o1", {"statement": "Max y"})
    assert updated_outcome is not None and updated_outcome.statement == "Max y"
    assert repo.update_step("nope", {"name": "x"}) is None
    assert repo.update_outcome("nope", {"statement": "x"}) is None


def test_delete_outcome_and_delete_step_return_false_when_missing():
    repo = _repo_with_graph()
    assert repo.delete_outcome("nope") is False
    assert repo.delete_step("nope") is False
    assert repo.delete_outcome("o1") is True
    assert repo.get_outcome("o1") is None


def test_delete_job_cascades_customer_outcomes():
    repo = _repo_with_graph()
    repo.add_customer_outcome(_linked_customer_outcome("co1", job_id="j1", step_id="s1"))
    repo.add_customer_outcome(_linked_customer_outcome("co2", job_id="other"))
    assert repo.delete_job("j1") is True
    assert repo.get_customer_outcome("co1") is None
    assert repo.get_customer_outcome("co2") is not None


def test_delete_step_cascades_customer_outcomes():
    repo = _repo_with_graph()
    repo.add_customer_outcome(_linked_customer_outcome("co1", job_id="j1", step_id="s1"))
    repo.add_customer_outcome(_linked_customer_outcome("co2", job_id="j1"))
    assert repo.delete_step("s1") is True
    assert repo.get_customer_outcome("co1") is None
    assert repo.get_customer_outcome("co2") is not None
    assert repo.get_customer_outcome("co1") is None
    assert repo.get_customer_outcome("co2") is not None


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


def test_evidence_crud_and_filters():
    repo = _repo_with_graph()
    repo.add_evidence(_evidence("e1", job_id="j1", step_id="s1", outcome_id="o1"))
    repo.add_evidence(_evidence("e2", job_id="j1"))
    assert repo.get_evidence("e1") is not None
    assert len(repo.list_evidence(job_id="j1")) == 2
    assert [item.id for item in repo.list_evidence(step_id="s1")] == ["e1"]
    assert [item.id for item in repo.list_evidence(outcome_id="o1")] == ["e1"]
    assert repo.delete_evidence("e1") is True
    assert repo.delete_evidence("e1") is False
    assert repo.get_evidence("e1") is None


def test_delete_job_unlinks_evidence():
    repo = _repo_with_graph()
    repo.add_evidence(_evidence("e1", job_id="j1", step_id="s1", outcome_id="o1"))
    repo.add_evidence(_evidence("e2", job_id="j1"))
    repo.add_evidence(_evidence("e3", job_id="other"))
    assert repo.delete_job("j1") is True
    #: Research evidence survives: references to the removed job, step, and
    #: outcome are nulled rather than the rows being destroyed.
    e1 = repo.get_evidence("e1")
    assert e1 is not None
    assert (e1.job_id, e1.step_id, e1.outcome_id) == (None, None, None)
    e2 = repo.get_evidence("e2")
    assert e2 is not None and e2.job_id is None
    assert repo.get_evidence("e3") is not None


def test_delete_outcome_unlinks_evidence():
    repo = _repo_with_graph()
    repo.add_evidence(_evidence("e1", job_id="j1", outcome_id="o1"))
    assert repo.delete_outcome("o1") is True
    e1 = repo.get_evidence("e1")
    assert e1 is not None
    assert e1.outcome_id is None


def test_reload_empties_in_memory_state() -> None:
    repo = InMemoryRepository()
    repo.add_job(Job(id="job-1", name="Job", description=""))
    repo.add_customer_outcome(_customer_outcome("co-1"))

    repo.reload()

    assert repo.list_jobs() == []
    assert repo.list_customer_outcomes() == []


def test_reload_is_safe_on_an_empty_repository() -> None:
    repo = InMemoryRepository()
    repo.reload()
    repo.reload()
    assert repo.list_jobs() == []


def test_rank_outcomes_puts_unscored_last_not_at_zero() -> None:
    """An unscored outcome is unknown, not a zero.

    Sorting an absent score as 0.0 would place it below a genuinely low
    opportunity and present a gap as a measurement, so the rank must keep
    unknown scores after every scored one.
    """
    scored_low = Outcome(
        id="o-low",
        job_id="job-1",
        statement="Minimize the wait when a build fails",
        importance=1.0,
        satisfaction=1.0,
        opportunity_score=1.0,
    )
    scored_high = Outcome(
        id="o-high",
        job_id="job-1",
        statement="Minimize the time to onboard when joining",
        importance=9.0,
        satisfaction=1.0,
        opportunity_score=17.0,
    )
    unscored = Outcome(
        id="o-none",
        job_id="job-1",
        statement="Minimize the noise when a deploy breaks",
    )

    ranked = rank_outcomes([unscored, scored_low, scored_high])

    assert [outcome.id for outcome in ranked] == ["o-high", "o-low", "o-none"]


def test_last_event_id_is_zero_before_any_write() -> None:
    assert InMemoryRepository().last_event_id() == 0


def test_each_write_is_given_its_own_event_id_in_append_order() -> None:
    repo = InMemoryRepository()

    ids: list[int] = []
    repo.add_job(Job(id="j1", name="Job"))
    ids.append(repo.last_event_id())
    repo.add_step(Step(id="s1", job_id="j1", name="Step", order=1))
    ids.append(repo.last_event_id())
    repo.update_step("s1", {"name": "Prepare"})
    ids.append(repo.last_event_id())
    repo.add_evidence(_evidence("e1", job_id="j1"))
    ids.append(repo.last_event_id())
    repo.delete_evidence("e1")
    ids.append(repo.last_event_id())

    assert ids == [1, 2, 3, 4, 5]


def test_a_write_that_changes_nothing_does_not_spend_an_event_id() -> None:
    repo = _repo_with_graph()
    before = repo.last_event_id()

    assert repo.update_job("missing", {"name": "x"}) is None
    assert repo.delete_step("missing") is False
    assert repo.mark_signal_read("missing") is None

    assert repo.last_event_id() == before


def test_stamping_the_same_signal_twice_spends_one_event_id() -> None:
    repo = _repo_with_graph()
    repo.add_signal(
        Signal(
            id="sig-1",
            kind=SignalKind.OUTCOME_SCORED,
            title="Outcome re-scored",
            fingerprint="fp",
        )
    )
    after_add = repo.last_event_id()

    assert repo.mark_signal_read("sig-1") is not None
    assert repo.last_event_id() == after_add + 1

    #: The second read changes nothing, so no event is appended and no id spent.
    assert repo.mark_signal_read("sig-1") is not None
    assert repo.last_event_id() == after_add + 1


def test_add_and_get_link() -> None:
    repo = InMemoryRepository()
    link = _link()
    created = repo.add_link(link)
    assert repo.get_link(created.id) == link


def test_list_links_filters_by_source_and_target() -> None:
    repo = InMemoryRepository()
    repo.add_link(
        _link(
            source_type="job",
            source_id="j1",
            target_type="outcome",
            target_id="o1",
            relationship=RelationshipType.RELATES_TO,
        )
    )
    repo.add_link(
        _link(
            source_type="job",
            source_id="j1",
            target_type="evidence",
            target_id="e1",
            relationship=RelationshipType.RELATES_TO,
        )
    )
    repo.add_link(
        _link(
            source_type="outcome",
            source_id="o1",
            target_type="job",
            target_id="j1",
            relationship=RelationshipType.RELATES_TO,
        )
    )

    by_source = [link.id for link in repo.list_links(source_type="job", source_id="j1")]
    assert len(by_source) == 2
    by_target = [link.id for link in repo.list_links(target_type="outcome", target_id="o1")]
    assert len(by_target) == 1
    assert repo.list_links(source_type="job", target_type="outcome") == [
        repo.get_link(by_source[0])
    ]


def test_remove_link_returns_true() -> None:
    repo = InMemoryRepository()
    link = _link()
    created = repo.add_link(link)
    assert repo.remove_link(created.id) is True
    assert repo.get_link(created.id) is None


def test_remove_link_unknown_returns_false() -> None:
    assert InMemoryRepository().remove_link("missing") is False


def test_adding_the_same_link_twice_raises_conflict() -> None:
    repo = InMemoryRepository()
    repo.add_link(_link())

    with pytest.raises(ConflictError):
        repo.add_link(_link())


def _candidate(id: str = "cand-1") -> CandidateSolution:
    return CandidateSolution(
        id=id,
        title="Guided setup checklist",
        hypothesis="A checklist will reduce the time to first value.",
        outcome_ids=["o-1", "o-2"],
        strategy_path=StrategyKind.DIFFERENTIATED,
        evidence_ids=["e-1"],
    )


def test_candidate_solution_round_trips_through_the_in_memory_repository() -> None:
    repo = InMemoryRepository()
    repo.add_candidate(_candidate())

    fetched = repo.get_candidate("cand-1")
    assert fetched is not None
    assert fetched.title == "Guided setup checklist"
    assert fetched.hypothesis == "A checklist will reduce the time to first value."
    assert fetched.outcome_ids == ["o-1", "o-2"]
    assert fetched.status is CandidateStatus.PROPOSED
    assert fetched.strategy_path is StrategyKind.DIFFERENTIATED
    assert fetched.evidence_ids == ["e-1"]
    assert [candidate.id for candidate in repo.list_candidates()] == ["cand-1"]


def test_candidate_status_can_be_updated_in_place() -> None:
    repo = InMemoryRepository()
    repo.add_candidate(_candidate())

    updated = repo.update_candidate("cand-1", {"status": "accepted"})

    assert updated is not None
    assert updated.status is CandidateStatus.ACCEPTED
    stored = repo.get_candidate("cand-1")
    assert stored is not None
    assert stored.status is CandidateStatus.ACCEPTED


def test_updating_a_missing_candidate_returns_none() -> None:
    repo = InMemoryRepository()
    assert repo.update_candidate("missing", {"status": "accepted"}) is None
    assert repo.get_candidate("missing") is None


def test_updating_a_candidate_keeps_its_id_and_creation_time() -> None:
    repo = InMemoryRepository()
    created = repo.add_candidate(CandidateSolution(title="Guided setup", hypothesis="Faster"))
    original_created_at = created.created_at

    updated = repo.update_candidate(created.id, {"status": "accepted"})

    assert updated is not None
    assert updated.id == created.id
    assert updated.created_at == original_created_at
    assert repo.get_candidate(updated.id) is updated
