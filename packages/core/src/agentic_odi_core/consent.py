"""Pause acting tool calls until the person using the studio has agreed.

The agent reads freely, but anything that changes the PM's workspace is a
proposal first. :class:`ConsentGate` keeps that rule in one place: a call is
requested, the person approves or declines it, and only then may it run.
Read-only tools pass straight through and never need a gate.

The acting set is derived from :class:`~agentic_odi_core.contract.ToolName`, so
a tool added to the contract is treated as acting until someone classifies it
as read-only.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, TypeVar

from agentic_odi_core.contract import ToolName
from agentic_odi_core.errors import ConsentRequired

T = TypeVar("T")

READ_ONLY_TOOLS: frozenset[str] = frozenset(
    {
        ToolName.GET_JOBS.value,
        ToolName.GET_JOB.value,
        ToolName.GET_JOB_MAP.value,
        ToolName.GET_STEP.value,
        ToolName.GET_OUTCOMES.value,
        ToolName.GET_OUTCOME.value,
        ToolName.GET_CUSTOMER_OUTCOME.value,
        ToolName.LIST_CUSTOMER_OUTCOMES.value,
        ToolName.GET_EVIDENCE.value,
        ToolName.LIST_EVIDENCE.value,
        ToolName.EVALUATE_OUTCOME.value,
        ToolName.GET_ODI_SCHEMA.value,
        ToolName.COMPUTE_OPPORTUNITY.value,
        ToolName.GET_FRAMEWORK_GUIDELINES.value,
        ToolName.GET_CAPABILITIES.value,
        ToolName.GET_OUTCOME_ALIGNMENTS.value,
        ToolName.GET_TRACEABILITY_REPORT.value,
    }
)

ACTING_TOOLS: frozenset[str] = frozenset(name.value for name in ToolName) - READ_ONLY_TOOLS


@dataclass(frozen=True)
class Proposal:
    """An acting tool call waiting for the PM's decision."""

    id: int
    tool: str
    arguments: Mapping[str, Any] = field(default_factory=dict)


class ConsentGate:
    """Hold acting calls until they are approved, one proposal at a time."""

    def __init__(self) -> None:
        self._pending: dict[int, Proposal] = {}
        self._approved: set[int] = set()
        self._next_id = 1

    def request(self, tool: str, arguments: Mapping[str, Any] | None = None) -> Proposal:
        """Queue an acting call. Nothing is executed here."""
        if tool not in ACTING_TOOLS:
            raise ValueError(f"{tool} is read-only and does not need consent")
        proposal = Proposal(id=self._next_id, tool=tool, arguments=dict(arguments or {}))
        self._next_id += 1
        self._pending[proposal.id] = proposal
        return proposal

    def pending(self) -> list[Proposal]:
        return list(self._pending.values())

    def approve(self, proposal: Proposal) -> None:
        if self._pending.pop(proposal.id, None) is None:
            raise ValueError(f"proposal {proposal.id} is not waiting for consent")
        self._approved.add(proposal.id)

    def decline(self, proposal: Proposal) -> bool:
        """Drop a pending proposal. Returns whether it was still waiting."""
        return self._pending.pop(proposal.id, None) is not None

    def execute(self, proposal: Proposal, action: Callable[[Mapping[str, Any]], T]) -> T:
        """Run an approved acting call exactly once."""
        if proposal.id in self._pending:
            raise ConsentRequired(
                f"{proposal.tool} is waiting for consent; approve or decline it first"
            )
        if proposal.id not in self._approved:
            raise ValueError(f"proposal {proposal.id} is not waiting for consent")
        self._approved.discard(proposal.id)
        return action(proposal.arguments)
