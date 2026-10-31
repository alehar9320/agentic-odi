"""The agent must not act on the workspace before the PM agrees."""

from __future__ import annotations

import pytest
from agentic_odi_core.consent import ACTING_TOOLS, READ_ONLY_TOOLS, ConsentGate
from agentic_odi_core.contract import TOOL_SPECS, ToolEffect, ToolName
from agentic_odi_core.errors import ConsentRequired
from agentic_odi_core.models import Job
from agentic_odi_core.repository import InMemoryRepository


def _repo_with_job() -> InMemoryRepository:
    repo = InMemoryRepository()
    repo.add_job(Job(id="job-1", name="Onboard customers"))
    return repo


def test_an_acting_call_mutates_nothing_until_consent() -> None:
    repo = _repo_with_job()
    gate = ConsentGate()
    proposal = gate.request(ToolName.DELETE_JOB.value, {"job_id": "job-1"})

    def delete(arguments):
        return repo.delete_job(arguments["job_id"])

    with pytest.raises(ConsentRequired):
        gate.execute(proposal, delete)
    assert repo.get_job("job-1") is not None

    gate.approve(proposal)
    assert gate.execute(proposal, delete) is True
    assert repo.get_job("job-1") is None


def test_a_declined_proposal_never_runs() -> None:
    repo = _repo_with_job()
    gate = ConsentGate()
    proposal = gate.request(ToolName.DELETE_JOB.value, {"job_id": "job-1"})

    assert gate.decline(proposal) is True

    with pytest.raises(ValueError):
        gate.execute(proposal, lambda arguments: repo.delete_job(arguments["job_id"]))
    assert repo.get_job("job-1") is not None


def test_an_approval_runs_only_once() -> None:
    gate = ConsentGate()
    proposal = gate.request(ToolName.ADD_JOB.value, {"name": "Onboard customers"})
    gate.approve(proposal)

    gate.execute(proposal, lambda arguments: arguments["name"])

    with pytest.raises(ValueError):
        gate.execute(proposal, lambda arguments: arguments["name"])


def test_read_only_tools_do_not_need_consent() -> None:
    gate = ConsentGate()

    with pytest.raises(ValueError):
        gate.request(ToolName.GET_JOBS.value)


def test_every_contract_tool_is_classified() -> None:
    assert set(TOOL_SPECS) == READ_ONLY_TOOLS | ACTING_TOOLS
    assert READ_ONLY_TOOLS.isdisjoint(ACTING_TOOLS)


def test_the_gate_agrees_with_the_contract_on_what_needs_consent() -> None:
    """The gate is derived from the contract, so the two cannot drift.

    A tool that changes the store must be acting, and a tool the contract
    declares read must not be. This is the assertion that would have caught the
    gate's hand-maintained set falling out of sync with ``TOOL_SPECS``.
    """
    contract_read = {name for name, spec in TOOL_SPECS.items() if spec.effect is ToolEffect.READ}
    assert READ_ONLY_TOOLS == contract_read
    assert ACTING_TOOLS == set(TOOL_SPECS) - contract_read
    # A read-only tool the contract knows about is never treated as acting.
    for name in contract_read:
        assert name not in ACTING_TOOLS
