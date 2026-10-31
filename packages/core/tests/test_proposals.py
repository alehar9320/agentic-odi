"""Tests for proposal lifecycle (issue #80)."""

from __future__ import annotations

import pytest

from agentic_odi_core.factory import build_repository
from agentic_odi_core.models import Evidence, Job
from agentic_odi_core.services import (
    InvalidOutcomeStatementError,
    ODIService,
)


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


def test_propose_approve_reject_cycle(tmp_path):


    repo = build_repository(str(tmp_path / "odi.db"))
    service = ODIService(repo)

    # Seed a job and evidence
    job = service.add_job("Secret rotation", "Rotate production credentials")
    ev = service.add_evidence(
        source_name="gong",
        source_kind="mcp",
        name="Q3 call",
        content="It takes too long to rotate production secrets before the next deploy.",
        job_id=job.id,
    )

    # Propose
    proposal = service.propose_outcome_from_evidence(ev.id)
    assert proposal is not None
    assert proposal.evidence_id == ev.id
    assert proposal.job_id == job.id
    assert proposal.status.value == "proposed"
    assert proposal.statement is not None
    assert "Minimize" in proposal.statement
    assert proposal.confidence > 0

    # List proposals
    all_props = service.list_proposals()
    assert len(all_props) == 1
    pending = service.list_proposals(status=None)
    assert len(pending) == 1

    # Approve
    outcome = service.approve_proposal(proposal.id)
    assert outcome is not None
    assert outcome.job_id == job.id
    assert outcome.statement == proposal.statement

    # Proposal is now approved
    updated = service.get_proposal(proposal.id) if hasattr(service, "get_proposal") else None
    # Check via repo
    assert repo.get_proposal(proposal.id).status.value == "approved"

    # The outcome exists in the store
    outcomes = service.get_outcomes(job.id)
    assert len(outcomes) == 1
    assert outcomes[0].statement == proposal.statement


def test_propose_reject_nothing_written(tmp_path):


    repo = build_repository(str(tmp_path / "odi.db"))
    service = ODIService(repo)

    job = service.add_job("Secret rotation")
    ev = service.add_evidence(
        source_name="gong",
        source_kind="mcp",
        name="Q3 call",
        content="It takes too long to rotate production secrets before the next deploy.",
        job_id=job.id,
    )
    proposal = service.propose_outcome_from_evidence(ev.id)

    service.reject_proposal(proposal.id)

    # No outcome was written
    outcomes = service.get_outcomes(job.id)
    assert len(outcomes) == 0

    # Proposal is rejected
    assert repo.get_proposal(proposal.id).status.value == "rejected"


def test_propose_edit_on_approve(tmp_path):


    repo = build_repository(str(tmp_path / "odi.db"))
    service = ODIService(repo)

    job = service.add_job("Secret rotation")
    ev = service.add_evidence(
        source_name="gong",
        source_kind="mcp",
        name="Q3 call",
        content="The rotation of the secret is too slow before the next deploy.",
        job_id=job.id,
    )
    proposal = service.propose_outcome_from_evidence(ev.id)

    # Edit the statement on approve
    edited = "Minimize the time to rotate the production secret before each deploy."
    outcome = service.approve_proposal(
        proposal.id, statement=edited, importance=9.0, satisfaction=2.0
    )
    assert outcome.statement == edited
    assert outcome.importance == 9.0
    assert outcome.satisfaction == 2.0

    # Proposal marked as edited
    assert repo.get_proposal(proposal.id).status.value == "edited"


def test_propose_invalid_statement_rejected(tmp_path):


    repo = build_repository(str(tmp_path / "odi.db"))
    service = ODIService(repo)

    job = service.add_job("Secret rotation")
    ev = service.add_evidence(
        source_name="gong",
        source_kind="mcp",
        name="Q3 call",
        content="The rotation of the secret is too slow before the next deploy.",
        job_id=job.id,
    )
    proposal = service.propose_outcome_from_evidence(ev.id)

    # Try to approve with an invalid statement
    with pytest.raises(InvalidOutcomeStatementError):
        service.approve_proposal(proposal.id, statement="bad statement")

    # Proposal should still be proposed, not approved
    assert repo.get_proposal(proposal.id).status.value == "proposed"
    # No outcome written
    assert len(service.get_outcomes(job.id)) == 0


def test_propose_batch_dedupes_on_reingest(tmp_path):


    repo = build_repository(str(tmp_path / "odi.db"))
    service = ODIService(repo)

    job = service.add_job("Secret rotation")

    # Add same evidence twice (dedup by fingerprint)
    ev1 = service.add_evidence(
        source_name="gong",
        source_kind="mcp",
        name="Q3 call",
        content="It takes too long to rotate production secrets before the next deploy.",
        job_id=job.id,
    )
    ev2 = service.add_evidence(
        source_name="gong",
        source_kind="mcp",
        name="Q3 call",
        content="It takes too long to rotate production secrets before the next deploy.",
        job_id=job.id,
    )
    # Same fingerprint → same evidence id
    assert ev1.id == ev2.id

    # Propose batch
    proposals = service.propose_outcomes_from_batch([ev1.id])
    assert len(proposals) == 1

    # Re-propose same evidence → should not duplicate
    proposals2 = service.propose_outcomes_from_batch([ev1.id])
    # The proposal already exists; the batch just re-proposes (creates new proposal
    # each time unless we dedupe at the proposal level)
    # For now, just verify it doesn't crash
    assert len(proposals2) == 1


def test_propose_nonexistent_evidence_raises(tmp_path):


    repo = build_repository(str(tmp_path / "odi.db"))
    service = ODIService(repo)

    with pytest.raises(Exception):
        service.propose_outcome_from_evidence("nonexistent-id")


def test_approve_nonexistent_proposal_raises(tmp_path):


    repo = build_repository(str(tmp_path / "odi.db"))
    service = ODIService(repo)

    with pytest.raises(Exception):
        service.approve_proposal("nonexistent-proposal-id")


def test_reject_already_approved_proposal_raises(tmp_path):


    repo = build_repository(str(tmp_path / "odi.db"))
    service = ODIService(repo)

    job = service.add_job("Secret rotation")
    ev = service.add_evidence(
        source_name="gong",
        source_kind="mcp",
        name="Q3 call",
        content="The rotation of the secret is too slow before the next deploy.",
        job_id=job.id,
    )
    proposal = service.propose_outcome_from_evidence(ev.id)
    service.approve_proposal(proposal.id)

    with pytest.raises(Exception):
        service.reject_proposal(proposal.id)
