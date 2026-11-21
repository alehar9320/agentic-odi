"""Tests for core domain models."""

from __future__ import annotations

from datetime import datetime

import pytest
from agentic_odi_core import Link as RootLink
from agentic_odi_core import RelationshipType as RootRelationshipType
from agentic_odi_core.errors import ValidationError
from agentic_odi_core.models import (
    LINK_RELATIONSHIP_TYPES,
    BusinessImpactCategory,
    BusinessValue,
    CustomerOutcome,
    CustomerValue,
    Direction,
    EntityType,
    Evidence,
    ExternalSystem,
    Link,
    RelationshipType,
    ValueMetric,
)
from pydantic import ValidationError as PydanticValidationError


def _customer_value(**overrides: object) -> CustomerValue:
    data: dict[str, object] = {
        "direction": Direction.MINIMIZE,
        "unit_of_measure": "minutes",
        "object_of_control": "time to resolve a support ticket",
        "statement": "Minimize the time it takes to resolve a support ticket",
        "importance": 8.0,
        "satisfaction": 4.0,
    }
    data.update(overrides)
    return CustomerValue(**data)  # type: ignore[arg-type]


def test_customer_value_opportunity_score_is_computed() -> None:
    assert _customer_value().opportunity_score == 12.0


def test_value_metric_opportunity_score_is_computed() -> None:
    metric = ValueMetric(
        name="resolution time",
        direction=Direction.MINIMIZE,
        unit_of_measure="minutes",
        importance=9.0,
        satisfaction=2.0,
    )
    assert metric.opportunity_score == 16.0


def test_customer_outcome_delegates_opportunity_score() -> None:
    outcome = CustomerOutcome(
        job_id="job-1",
        customer_value=_customer_value(importance=6.0, satisfaction=1.0),
        business_value=BusinessValue(
            category=BusinessImpactCategory.COST_REDUCTION,
            statement="Reduce support cost",
        ),
    )
    assert outcome.opportunity_score == 11.0


def test_evidence_defaults_to_medium_impact_and_claimed_confidence() -> None:
    evidence = Evidence(
        source_name="demo",
        source_kind="demo",
        name="fixture",
        content="A captured quote",
    )
    assert evidence.impact == "medium"
    assert evidence.confidence == "claimed"


def test_evidence_accepts_explicit_impact_and_confidence() -> None:
    evidence = Evidence(
        source_name="demo",
        source_kind="demo",
        name="fixture",
        content="A captured quote",
        impact="high",
        confidence="verified",
    )
    assert evidence.impact == "high"
    assert evidence.confidence == "verified"


def test_evidence_rejects_unknown_impact_and_confidence() -> None:
    with pytest.raises(PydanticValidationError):
        Evidence(
            source_name="demo",
            source_kind="demo",
            name="fixture",
            content="A captured quote",
            impact="extreme",
        )
    with pytest.raises(PydanticValidationError):
        Evidence(
            source_name="demo",
            source_kind="demo",
            name="fixture",
            content="A captured quote",
            confidence="maybe",
        )


def test_link_round_trips_with_relationship_type() -> None:
    link = Link(
        source_type=EntityType.EVIDENCE,
        source_id="evidence-1",
        target_type=EntityType.OUTCOME,
        target_id="outcome-1",
        relationship_type=RelationshipType.EVIDENCE_FOR,
        external_system=ExternalSystem.JIRA,
        external_id="EXT-42",
        preview={"title": "Resolved faster"},
    )
    assert link.relationship_type is RelationshipType.EVIDENCE_FOR
    assert link.relationship_type.value == "evidence_for"
    assert link.source_type is EntityType.EVIDENCE
    assert link.target_type is EntityType.OUTCOME
    assert isinstance(link.created_at, datetime)
    assert link.id is not None

    restored = Link.model_validate_json(link.model_dump_json())
    assert restored == link
    assert restored.relationship_type is RelationshipType.EVIDENCE_FOR
    assert restored.external_system is ExternalSystem.JIRA
    assert restored.external_id == "EXT-42"
    assert restored.preview == {"title": "Resolved faster"}


def test_link_is_exported_at_package_root() -> None:
    assert RootLink is Link
    assert RootRelationshipType is RelationshipType


def test_relationship_type_is_closed_to_five_values() -> None:
    assert {member.value for member in RelationshipType} == {
        "evidence_for",
        "outcome_of",
        "blocked_by",
        "duplicates",
        "relates_to",
    }


def test_link_relationship_type_constant_matches_enum() -> None:
    assert LINK_RELATIONSHIP_TYPES == [member.value for member in RelationshipType]


def test_link_relationship_type_accepts_a_string_value() -> None:
    link = Link(
        source_type="job",
        source_id="job-1",
        target_type="job",
        target_id="job-2",
        relationship_type="duplicates",
    )

    assert link.relationship_type is RelationshipType.DUPLICATES


def test_entity_type_has_no_candidate_member() -> None:
    assert {member.value for member in EntityType} == {
        "job",
        "step",
        "outcome",
        "evidence",
        "segment",
        "strategy",
    }


def test_a_self_link_is_rejected() -> None:
    with pytest.raises(ValidationError, match="cannot point at itself"):
        Link(
            source_type=EntityType.EVIDENCE,
            source_id="evidence-1",
            target_type=EntityType.EVIDENCE,
            target_id="evidence-1",
            relationship_type=RelationshipType.EVIDENCE_FOR,
        )


def test_an_out_of_matrix_pair_is_rejected_naming_the_allowed_targets() -> None:
    with pytest.raises(ValidationError) as excinfo:
        Link(
            source_type=EntityType.OUTCOME,
            source_id="outcome-1",
            target_type=EntityType.EVIDENCE,
            target_id="evidence-1",
            relationship_type=RelationshipType.EVIDENCE_FOR,
        )
    message = str(excinfo.value)
    assert "evidence_for" in message
    assert "outcome" in message
    assert "evidence" in message
    assert "allowed targets" in message


def test_a_duplicate_link_must_join_the_same_entity_type() -> None:
    with pytest.raises(ValidationError, match="same entity type"):
        Link(
            source_type=EntityType.OUTCOME,
            source_id="outcome-1",
            target_type=EntityType.JOB,
            target_id="job-1",
            relationship_type=RelationshipType.DUPLICATES,
        )


def test_a_one_sided_external_reference_is_rejected() -> None:
    with pytest.raises(ValidationError, match="external_system and external_id"):
        Link(
            source_type=EntityType.EVIDENCE,
            source_id="evidence-1",
            target_type=EntityType.OUTCOME,
            target_id="outcome-1",
            relationship_type=RelationshipType.EVIDENCE_FOR,
            external_system=ExternalSystem.JIRA,
        )


def test_a_two_sided_external_reference_validates() -> None:
    link = Link(
        source_type=EntityType.OUTCOME,
        source_id="outcome-1",
        target_type=EntityType.JOB,
        target_id="job-1",
        relationship_type=RelationshipType.RELATES_TO,
        external_system=ExternalSystem.LINEAR,
        external_id="LIN-7",
    )
    assert link.external_system is ExternalSystem.LINEAR
    assert link.external_id == "LIN-7"


def test_a_blocked_by_link_accepts_any_pair() -> None:
    link = Link(
        source_type=EntityType.SEGMENT,
        source_id="segment-1",
        target_type=EntityType.STRATEGY,
        target_id="strategy-1",
        relationship_type=RelationshipType.BLOCKED_BY,
    )
    assert link.relationship_type is RelationshipType.BLOCKED_BY
