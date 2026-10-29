"""Tests for the actionable ``EvidenceNotFoundError``."""

from __future__ import annotations

import pytest
from agentic_odi_core import EvidenceNotFoundError, evidence_not_found
from agentic_odi_core.errors import NotFoundError, OdiError
from agentic_odi_core.repository import InMemoryRepository
from agentic_odi_core.services import ODIService


@pytest.fixture
def service() -> ODIService:
    return ODIService(InMemoryRepository())


def test_error_is_catchable_as_value_error() -> None:
    """Callers written against the old bare-``ValueError`` behaviour still work."""
    err = EvidenceNotFoundError("ev-1")

    assert isinstance(err, ValueError)
    assert isinstance(err, NotFoundError)
    assert isinstance(err, OdiError)


def test_error_exposes_the_evidence_id() -> None:
    err = EvidenceNotFoundError("ev-1")

    assert err.evidence_id == "ev-1"
    assert err.resource_id == "ev-1"
    assert err.kind == "evidence"


def test_error_message_includes_the_evidence_id() -> None:
    err = EvidenceNotFoundError("ev-1")

    assert "ev-1" in str(err)


def test_error_message_includes_the_hint() -> None:
    err = EvidenceNotFoundError("ev-1", "Try list_evidence() first.")

    assert "ev-1" in str(err)
    assert "Try list_evidence() first." in str(err)
    assert err.hint == "Try list_evidence() first."


def test_hint_is_optional_and_defaults_to_empty() -> None:
    err = EvidenceNotFoundError("ev-1")

    assert err.hint == ""
    assert str(err).endswith("ev-1")


def test_hint_is_appended_after_the_identifier() -> None:
    err = EvidenceNotFoundError("ev-1", "Try list_evidence() first.")

    assert str(err) == "evidence not found: ev-1. Try list_evidence() first."


def test_evidence_not_found_message_helper_includes_the_hint() -> None:
    assert evidence_not_found("ev-1") == "Evidence not found: ev-1"
    assert (
        evidence_not_found("ev-1", "Try list_evidence() first.")
        == "Evidence not found: ev-1. Try list_evidence() first."
    )


def test_service_delete_evidence_raises_with_a_hint(service) -> None:
    with pytest.raises(EvidenceNotFoundError) as caught:
        service.delete_evidence("missing-evidence")

    assert caught.value.evidence_id == "missing-evidence"
    assert caught.value.hint
    assert "list_evidence" in caught.value.hint


def test_service_promote_evidence_raises_with_a_hint(service) -> None:
    with pytest.raises(EvidenceNotFoundError) as caught:
        service.promote_evidence("missing-evidence", "job")

    assert caught.value.evidence_id == "missing-evidence"
    assert caught.value.hint
    assert "list_evidence" in caught.value.hint
