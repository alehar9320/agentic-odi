"""Later-increment seams refuse rather than invent a default.

B3 (bands), B4.1 (confidence) and B6.1 (deltas) each wait on an open decision.
Until that decision is approved, the seam must say so — never return a
fabricated band, class or direction. These tests pin the refusal and the reason
it names, so a later implementation cannot quietly start guessing.
"""

from __future__ import annotations

import pytest
from agentic_odi_core.errors import OdiError
from agentic_odi_core.models import Outcome, ScoreSnapshot
from agentic_odi_core.trust import (
    BootstrapConvention,
    ConfidenceTable,
    DeltaSemantics,
    TrustContractPendingError,
    classify_confidence,
    opportunity_interval,
    outcome_delta,
)

_STATEMENT = "Minimize the time it takes to onboard a new engineer when they join."


def _outcome(**overrides: object) -> Outcome:
    base: dict[str, object] = {
        "job_id": "job-1",
        "statement": _STATEMENT,
        "importance": 8.0,
        "satisfaction": 6.0,
    }
    base.update(overrides)
    return Outcome(**base)


def test_pending_error_is_an_odi_error_and_names_the_gate() -> None:
    err = TrustContractPendingError("opportunity_interval", BootstrapConvention)

    assert isinstance(err, OdiError)
    assert err.capability == "opportunity_interval"
    assert err.decision == BootstrapConvention
    assert "opportunity_interval" in str(err)
    assert BootstrapConvention in str(err)


def test_opportunity_interval_refuses_until_the_convention_is_approved() -> None:
    with pytest.raises(TrustContractPendingError) as caught:
        opportunity_interval(_outcome())

    assert caught.value.decision == BootstrapConvention


def test_classify_confidence_refuses_until_the_table_is_approved() -> None:
    with pytest.raises(TrustContractPendingError) as caught:
        classify_confidence(_outcome())

    assert caught.value.decision == ConfidenceTable


def test_outcome_delta_refuses_until_the_semantics_are_approved() -> None:
    snapshots = [ScoreSnapshot(outcome_id="outcome-1", importance=8.0, satisfaction=6.0)]

    with pytest.raises(TrustContractPendingError) as caught:
        outcome_delta(snapshots)

    assert caught.value.decision == DeltaSemantics


def test_the_seams_are_exported_from_the_package_root() -> None:
    import agentic_odi_core as core

    for name in (
        "OpportunityInterval",
        "OutcomeDelta",
        "TrustContractPendingError",
        "opportunity_interval",
        "classify_confidence",
        "outcome_delta",
    ):
        assert name in core.__all__
        assert hasattr(core, name)
