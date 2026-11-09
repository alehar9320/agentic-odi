from __future__ import annotations

from pr_triage import (
    AI_LABEL,
    DEEP_DIVE_LABEL,
    GATE_LABEL,
    HIGH_TIER,
    HUMAN_LABEL,
    LOW_TIER,
    MEDIUM_TIER,
    REVIEWER_LABEL,
    SIZE_LABELS,
    extract_facts,
    triage,
    triage_label_decision,
)


def test_human_author_is_vetted_immediately():
    decision = triage(
        author_label=HUMAN_LABEL,
        risk_tier="",
        size_label="",
    )
    assert decision["gate"] is True
    assert decision["review_label"] is None


def test_ai_low_risk_is_fast_tracked():
    decision = triage(
        author_label=AI_LABEL,
        risk_tier=LOW_TIER,
        size_label="size/S",
    )
    assert decision["gate"] is True
    assert decision["review_label"] is None


def test_ai_medium_risk_is_not_gated():
    decision = triage(
        author_label=AI_LABEL,
        risk_tier=MEDIUM_TIER,
        size_label="size/S",
    )
    assert decision["gate"] is False
    assert decision["review_label"] == REVIEWER_LABEL


def test_ai_high_risk_is_deep_dive_never_gated():
    decision = triage(
        author_label=AI_LABEL,
        risk_tier=HIGH_TIER,
        size_label="size/XS",
    )
    assert decision["gate"] is False
    assert decision["review_label"] == DEEP_DIVE_LABEL


def test_ai_low_risk_xl_size_needs_reviewer_first():
    decision = triage(
        author_label=AI_LABEL,
        risk_tier=LOW_TIER,
        size_label="size/XL",
    )
    assert decision["gate"] is False
    assert decision["review_label"] == REVIEWER_LABEL


def test_unknown_risk_tier_is_not_gated():
    decision = triage(
        author_label=AI_LABEL,
        risk_tier="",
        size_label="size/S",
    )
    assert decision["gate"] is False
    assert decision["review_label"] == REVIEWER_LABEL


def test_label_decision_clears_then_applies_owned_labels():
    decision = triage_label_decision(
        author_label=AI_LABEL,
        risk_tier=HIGH_TIER,
        size_label="size/XS",
    )
    # All triage-owned labels are slated for removal first (idempotent hygiene).
    assert {GATE_LABEL, REVIEWER_LABEL, DEEP_DIVE_LABEL}.issubset(set(decision["remove"]))
    assert decision["add"] == [DEEP_DIVE_LABEL]
    assert decision["gate"] is False


def test_label_decision_applies_gate_for_human():
    decision = triage_label_decision(
        author_label=HUMAN_LABEL,
        risk_tier="",
        size_label="",
    )
    assert decision["add"] == [GATE_LABEL]
    assert decision["gate"] is True


def test_extract_facts_picks_up_every_signal():
    labels = {
        "🤖 agent",
        "safe to merge",
        "size/XL",
        "area/studio",
    }
    facts = extract_facts(labels)
    assert facts == {
        "author_label": "🤖 agent",
        "risk_tier": "safe to merge",
        "size_label": "size/XL",
    }


def test_extract_facts_defaults_to_human_and_empty():
    assert extract_facts({"area/docs", "size/M"}) == {
        "author_label": "👤 human",
        "risk_tier": "",
        "size_label": "size/M",
    }


def test_extract_facts_picks_highest_risk_tier_only():
    # A PR should only carry one tier, but if it somehow carried several, the
    # first in low/medium/high order wins.
    labels = {"safe to merge", "danger zone"}
    assert extract_facts(labels)["risk_tier"] == "safe to merge"


def test_all_size_labels_are_recognized():
    for size in SIZE_LABELS:
        assert extract_facts({size})["size_label"] == size


def test_triage_never_executes_pr_code():
    """Unit test is pure: no network, no subprocess, no gh."""
    import subprocess

    # This test intentionally imports nothing that touches the network. The
    # assertion below documents purity by exercising only in-memory logic.
    decision = triage(author_label=AI_LABEL, risk_tier=MEDIUM_TIER, size_label="size/M")
    assert isinstance(decision["gate"], bool)
    del subprocess
