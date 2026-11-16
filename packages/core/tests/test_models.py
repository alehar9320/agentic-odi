"""Tests for core domain models."""

from __future__ import annotations

from datetime import datetime

import pytest
from agentic_odi_core import Link as RootLink
from agentic_odi_core import RelationshipType as RootRelationshipType
from agentic_odi_core.models import (
    LINK_RELATIONSHIP_TYPES,
    BusinessImpactCategory,
    BusinessValue,
    CustomerOutcome,
    CustomerValue,
    Direction,
    Evidence,
    Link,
    RelationshipType,
    ValueMetric,
)
from pydantic import ValidationError


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
    with pytest.raises(ValidationError):
        Evidence(
            source_name="demo",
            source_kind="demo",
            name="fixture",
            content="A captured quote",
            impact="extreme",
        )
    with pytest.raises(ValidationError):
        Evidence(
            source_name="demo",
            source_kind="demo",
            name="fixture",
            content="A captured quote",
            confidence="maybe",
        )


def test_link_round_trips_with_relationship_type() -> None:
    link = Link(
        source_type="evidence",
        source_id="evidence-1",
        target_type="outcome",
        target_id="outcome-1",
        relationship_type=RelationshipType.serves,
        external_system="jira",
        external_id="EXT-42",
        preview={"title": "Resolved faster"},
    )
    assert link.relationship_type == RelationshipType.serves
    assert link.relationship_type.value == "serves"
    assert link.source_type == "evidence"
    assert link.target_type == "outcome"
    assert isinstance(link.created_at, datetime)
    assert link.id is not None

    restored = Link.model_validate_json(link.model_dump_json())
    assert restored == link
    assert restored.relationship_type is RelationshipType.serves
    assert restored.external_system == "jira"
    assert restored.external_id == "EXT-42"
    assert restored.preview == {"title": "Resolved faster"}


def test_link_is_exported_at_package_root() -> None:
    assert RootLink is Link
    assert RootRelationshipType is RelationshipType


def test_link_relationship_type_has_all_values() -> None:
    expected = {
        "references",
        "serves",
        "blocked_by",
        "blocking",
        "duplicates",
        "relates_to",
        "implements",
        "validates",
        "evidence_for",
        "outcome_of",
        "external_jira",
        "external_linear",
        "external_jpd",
        "external_github",
        "external_notion",
    }
    assert {member.value for member in RelationshipType} == expected


def test_relationship_type_is_str_enum() -> None:
    assert RelationshipType.references == "references"
    assert isinstance(RelationshipType.references, str)


def test_link_relationship_type_constant_matches_enum() -> None:
    assert LINK_RELATIONSHIP_TYPES == [m.value for m in RelationshipType]
    assert "external_notion" in LINK_RELATIONSHIP_TYPES


def test_link_defaults_are_populated() -> None:
    link = Link(
        source_type="evidence",
        source_id="ev-1",
        target_type="outcome",
        target_id="out-1",
        relationship_type=RelationshipType.evidence_for,
    )

    assert link.id
    assert link.external_system is None
    assert link.external_id is None
    assert link.preview is None
    assert link.created_at is not None


def test_link_accepts_external_system_and_preview() -> None:
    link = Link(
        source_type="outcome",
        source_id="out-1",
        target_type="linear_issue",
        target_id="LIN-1",
        relationship_type=RelationshipType.external_linear,
        external_system="linear",
        external_id="LIN-1",
        preview={"title": "Implement onboarding", "state": "In Progress"},
    )

    assert link.external_system == "linear"
    assert link.external_id == "LIN-1"
    assert link.preview == {"title": "Implement onboarding", "state": "In Progress"}


def test_link_relationship_type_accepts_string_value() -> None:
    link = Link(
        source_type="job",
        source_id="job-1",
        target_type="job",
        target_id="job-2",
        relationship_type="duplicates",
    )

    assert link.relationship_type is RelationshipType.duplicates
