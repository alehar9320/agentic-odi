"""The real spine stages: they read and write the store, and never fabricate.

Each stage is exercised against a real SQLite store, including the two promises
that make the loop trustworthy: an unresolved id is refused rather than answered
with a placeholder, and an unmeasured value stays ``None`` rather than becoming
a zero.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from agentic_odi_core import ODIService
from agentic_odi_core.factory import build_repository
from agentic_odi_core.spine_stages import (
    SpineStageError,
    StoreBetTracker,
    StoreBriefRenderer,
    StoreDecisionRecorder,
    StoreMeasurementReader,
    StoreScoreSampler,
)


@pytest.fixture
def repo(tmp_path: Path):
    r = build_repository(str(tmp_path / "stages.db"))
    yield r
    r.close()


@pytest.fixture
def outcome(repo):
    service = ODIService(repo)
    job = service.add_job("Onboard customers")
    return service.add_outcome(
        job.id,
        "Minimize the time it takes to onboard when a customer signs up.",
        importance=9.0,
        satisfaction=4.0,
    )


def test_the_score_sampler_reads_the_outcomes_scores(repo, outcome) -> None:
    sample = StoreScoreSampler(repo).sample(outcome.id)
    assert sample.importance == 9.0
    assert sample.satisfaction == 4.0
    assert sample.opportunity_score == 14.0
    assert sample.sample_size is None  # unknown, not a fabricated zero


def test_the_score_sampler_refuses_an_unknown_outcome(repo) -> None:
    with pytest.raises(SpineStageError):
        StoreScoreSampler(repo).sample("nope")


def test_the_brief_renderer_reports_the_opportunity_with_its_basis(repo, outcome) -> None:
    brief = StoreBriefRenderer(repo).render(outcome.id)
    figures = {figure.name: figure for figure in brief.figures}
    assert figures["opportunity_score"].value == 14.0
    assert figures["opportunity_score"].basis
    assert figures["decisions"].value == 0.0


def test_the_brief_renderer_refuses_an_unknown_subject(repo) -> None:
    with pytest.raises(SpineStageError):
        StoreBriefRenderer(repo).render("nope")


def test_the_decision_recorder_persists_and_returns_a_decision(repo, outcome) -> None:
    decision = StoreDecisionRecorder(repo).record(
        subject_id=outcome.id, choice="build", rationale="underserved"
    )
    assert repo.get_decision(decision.id).choice == "build"


def test_the_decision_recorder_refuses_an_unknown_subject(repo) -> None:
    with pytest.raises(SpineStageError):
        StoreDecisionRecorder(repo).record(subject_id="nope", choice="x", rationale="y")


def test_the_bet_tracker_refuses_an_unknown_decision(repo) -> None:
    with pytest.raises(SpineStageError):
        StoreBetTracker(repo).track(decision_id="nope", statement="s", metric="m")


def test_the_measurement_reader_reports_nothing_yet_for_an_unmeasured_bet(repo, outcome) -> None:
    decision = StoreDecisionRecorder(repo).record(
        subject_id=outcome.id, choice="build", rationale="why"
    )
    bet = StoreBetTracker(repo).track(
        decision_id=decision.id, statement="activation rises", metric="activation"
    )
    measurement = StoreMeasurementReader(repo).measure(bet.id)
    assert measurement.metric == "activation"
    assert measurement.value is None


def test_the_measurement_reader_refuses_an_unknown_bet(repo) -> None:
    with pytest.raises(SpineStageError):
        StoreMeasurementReader(repo).measure("nope")


def test_the_loop_persists_across_a_reopen(tmp_path: Path) -> None:
    path = str(tmp_path / "loop.db")
    repo = build_repository(path)
    service = ODIService(repo)
    job = service.add_job("Onboard customers")
    outcome = service.add_outcome(
        job.id,
        "Minimize the time it takes to onboard when a customer signs up.",
        importance=9.0,
        satisfaction=4.0,
    )
    decision = StoreDecisionRecorder(repo).record(
        subject_id=outcome.id, choice="build", rationale="underserved"
    )
    bet = StoreBetTracker(repo).track(
        decision_id=decision.id, statement="activation rises", metric="activation"
    )
    repo.close()

    reopened = build_repository(path)
    reloaded_decision = reopened.get_decision(decision.id)
    reloaded_bet = reopened.get_bet(bet.id)
    assert reloaded_decision is not None and reloaded_decision.subject_id == outcome.id
    assert reloaded_bet is not None and reloaded_bet.decision_id == decision.id
    reopened.close()
