"""Tests for the evidence-to-outcome proposal engine (issue #80)."""

from __future__ import annotations

from agentic_odi_core.mapping import (
    HeuristicProposalStrategy,
    OutcomeProposal,
    ProposalStatus,
)
from agentic_odi_core.models import Direction, Evidence, Job, JobStage, Step


def _evidence(**overrides) -> Evidence:
    data = dict(
        id="e1",
        source_name="gong",
        source_kind="mcp",
        item_type="manual",
        name="Q3 call",
        content="It takes too long to rotate production secrets before the next deploy.",
    )
    data.update(overrides)
    return Evidence(**data)


def _job(name: str, description: str | None = None, job_id: str = "j1") -> Job:
    return Job(id=job_id, name=name, description=description)


def _step(
    name: str, step_id: str = "s1", job_id: str = "j1", stage: JobStage | None = None
) -> Step:
    return Step(id=step_id, job_id=job_id, name=name, order=1, stage=stage)


def test_proposal_model_roundtrips():
    proposal = OutcomeProposal(
        evidence_id="e1",
        job_id="j1",
        step_id="s1",
        statement="Minimize the time it takes to rotate production secrets before the next deploy.",
        direction=Direction.MINIMIZE,
        unit_of_measure="time",
        object_of_control="production secrets",
        contextual_clarifier="before the next deploy",
        importance=8.0,
        satisfaction=3.0,
        confidence=0.7,
        rationale="test rationale",
        quote="It takes too long to rotate production secrets.",
        source_name="gong",
        status=ProposalStatus.PROPOSED,
    )
    data = proposal.model_dump()
    restored = OutcomeProposal.model_validate(data)
    assert restored.id == proposal.id
    assert restored.status == ProposalStatus.PROPOSED
    assert restored.direction == Direction.MINIMIZE


def test_proposal_status_values():
    assert ProposalStatus.PROPOSED == "proposed"
    assert ProposalStatus.APPROVED == "approved"
    assert ProposalStatus.REJECTED == "rejected"
    assert ProposalStatus.EDITED == "edited"


def test_object_of_control_prefers_the_action_verb_phrase():
    extract = HeuristicProposalStrategy._find_object_of_control
    assert extract("rotate production secrets before the next deploy") == "production secrets"
    assert (
        extract("fix the invoice reconciliation when the batch fails") == "invoice reconciliation"
    )


def test_object_of_control_falls_back_to_the_noun_phrase():
    extract = HeuristicProposalStrategy._find_object_of_control
    assert extract("the quarterly report.") == "quarterly report"
    assert extract("nothing recognizable here") is None


def test_linked_evidence_routes_to_its_own_job():
    strategy = HeuristicProposalStrategy()
    jobs = [_job("Unrelated name", description="nothing shared")]
    evidence = _evidence(
        name="Ticket 41",
        content="It takes too long to rotate production secrets before the next deploy.",
        job_id="j1",
    )

    assert strategy._route_to_job(evidence, jobs) == ("j1", jobs[0])


def test_routes_to_job_by_term_overlap():
    strategy = HeuristicProposalStrategy()
    jobs = [_job("Secret rotation", "How teams rotate production credentials")]
    steps = [_step("Confirm readiness")]
    evidence = _evidence(
        content="It takes too long to rotate production secrets before the next deploy."
    )
    proposal = strategy.propose(evidence, jobs, steps)
    assert proposal is not None
    assert proposal.job_id == "j1"
    assert proposal.statement is not None
    assert "Minimize" in proposal.statement


def test_routes_to_step_within_job():
    strategy = HeuristicProposalStrategy()
    jobs = [_job("Secret rotation")]
    steps = [_step("Confirm readiness", stage=JobStage.CONFIRM)]
    evidence = _evidence(content="The rotation of the secret is too slow before the next deploy.")
    proposal = strategy.propose(evidence, jobs, steps)
    assert proposal is not None
    assert proposal.job_id == "j1"


def test_unmatched_record_returns_none():
    strategy = HeuristicProposalStrategy()
    jobs = [_job("Customer onboarding", "Welcome new users")]
    evidence = _evidence(content="The database connection pool is exhausted under load.")
    proposal = strategy.propose(evidence, jobs, [])
    assert proposal is None


def test_no_complaint_pattern_returns_none():
    strategy = HeuristicProposalStrategy()
    jobs = [_job("Secret rotation")]
    evidence = _evidence(content="Everything works fine and is easy to use.")
    proposal = strategy.propose(evidence, jobs, [])
    assert proposal is None


def test_invalid_statement_not_created():
    strategy = HeuristicProposalStrategy()
    # Evidence with a complaint but no measurable object — should not produce a valid proposal
    jobs = [_job("Data entry")]
    evidence = _evidence(content="It is hard when things happen.")
    proposal = strategy.propose(evidence, jobs, [])
    # May or may not produce a proposal depending on parsing, but if it does,
    # the statement must be valid ODI format
    if proposal is not None:
        from agentic_odi_core.evaluation import evaluate_outcome_statement

        verdict = evaluate_outcome_statement(proposal.statement)
        assert verdict["valid"]


def test_importance_satisfaction_are_suggestions():
    strategy = HeuristicProposalStrategy()
    jobs = [_job("Secret rotation")]
    evidence = _evidence(
        content="It takes too long to rotate production secrets before the next deploy. "
        "We cannot do it without a workaround and multiple people are stuck."
    )
    proposal = strategy.propose(evidence, jobs, [])
    assert proposal is not None
    assert proposal.importance is not None
    assert proposal.satisfaction is not None
    assert 1.0 <= proposal.importance <= 10.0
    assert 1.0 <= proposal.satisfaction <= 10.0
    assert 0.0 <= proposal.confidence <= 1.0
    assert proposal.rationale
    assert proposal.quote


def test_heuristic_is_deterministic():
    strategy = HeuristicProposalStrategy()
    jobs = [_job("Secret rotation")]
    steps = [_step("Confirm readiness")]
    evidence = _evidence(content="The rotation of the secret is too slow before the next deploy.")
    p1 = strategy.propose(evidence, jobs, steps)
    p2 = strategy.propose(evidence, jobs, steps)
    assert p1 is not None and p2 is not None
    assert p1.statement == p2.statement
    assert p1.importance == p2.importance
    assert p1.satisfaction == p2.satisfaction


def test_proposal_strategy_protocol_is_satisfied():
    """HeuristicProposalStrategy satisfies the ProposalStrategy protocol."""
    strategy: HeuristicProposalStrategy = HeuristicProposalStrategy()
    assert callable(strategy.propose)
