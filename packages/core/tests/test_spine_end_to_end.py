"""H3 — one end-to-end test of the spine over the real code paths.

This drives the pipeline that exists today — quote → candidate → outcome — using
the *real* store (SQLite, so events replay) and the real service, with only the
model boundary replaced by the fixture extractor. It asserts the invariants the
product rests on:

* extraction proposes; it never writes an outcome,
* acceptance goes through ``ODIService.add_outcome`` and links the evidence,
* re-extraction is idempotent and preserves a human's decision,
* a reload rebuilds the same candidates from the event log.

It deliberately stops at ``outcome``. The stages beyond it (score, brief,
decision, bet, measure) are still stubs, and this test asserts they refuse
rather than fabricating a number — so the test grows as the spine does, instead
of being written against doubles that would have to be thrown away.
"""

from __future__ import annotations

import pytest
from agentic_odi_core import (
    FixtureStatementExtractor,
    Proposal,
    StageNotImplemented,
    build_repository,
    build_spine,
    seam_inventory,
)
from agentic_odi_core.models import CandidateStatus
from agentic_odi_core.services import ODIService
from agentic_odi_core.spine import SPINE_ORDER, CandidateOutcome

VALID = "Minimize the time it takes to onboard a new customer when they sign up."


def _require_id(candidate: CandidateOutcome) -> str:
    """A proposed candidate from the fixture always carries its id."""
    assert candidate.candidate_id is not None
    return candidate.candidate_id


INVALID = "This is bad."
QUOTE = f"{VALID} {INVALID}"


def _repo(tmp_path):
    return build_repository(str(tmp_path / "spine.db"))


def test_the_whole_pipeline_runs_on_real_code_paths(tmp_path) -> None:
    repo = _repo(tmp_path)
    service = ODIService(repo)
    job = service.add_job("Onboard customers")
    spine = build_spine(repo, extractor=FixtureStatementExtractor())

    # 1. quote -> candidates. Nothing is an outcome yet.
    candidates = spine.extractor.extract(QUOTE, quote_id="q1", job_id=job.id)
    assert {c.status for c in candidates} == {"proposed", "rejected"}
    assert repo.outcomes == {}

    # 2. candidate -> outcome, through the service's validator.
    proposed = next(c for c in candidates if c.status == "proposed")
    outcome = spine.acceptor.accept(_require_id(proposed), importance=9.0, satisfaction=4.0)
    assert outcome.statement == VALID
    assert outcome.opportunity_score == 14.0
    assert len(repo.outcomes) == 1

    # 3. the candidate records its decision and links the outcome.
    decided = repo.get_candidate(_require_id(proposed))
    assert decided is not None
    assert decided.status is CandidateStatus.ACCEPTED
    assert decided.outcome_id == outcome.id

    # 4. re-extraction adds nothing and does not reset the decision.
    again = spine.extractor.extract(QUOTE, quote_id="q1", job_id=job.id)
    assert len(again) == len(candidates)
    re_read = repo.get_candidate(_require_id(proposed))
    assert re_read is not None and re_read.status is CandidateStatus.ACCEPTED

    repo.close()


def test_reload_rebuilds_candidates_from_the_event_log(tmp_path) -> None:
    path = str(tmp_path / "spine.db")
    repo = build_repository(path)
    service = ODIService(repo)
    job = service.add_job("Onboard customers")
    spine = build_spine(repo, extractor=FixtureStatementExtractor())
    candidates = spine.extractor.extract(QUOTE, quote_id="q1", job_id=job.id)
    proposed = next(c for c in candidates if c.status == "proposed")
    outcome = spine.acceptor.accept(_require_id(proposed), importance=8.0, satisfaction=5.0)
    repo.commit()
    repo.close()

    reopened = build_repository(path)
    reloaded = reopened.list_candidates(quote_id="q1")
    assert len(reloaded) == len(candidates)
    decided = reopened.get_candidate(_require_id(proposed))
    assert decided is not None
    assert decided.status is CandidateStatus.ACCEPTED
    assert decided.outcome_id == outcome.id
    assert len(reopened.outcomes) == 1
    reopened.close()


def test_the_inventory_reports_exactly_what_this_build_can_do(tmp_path) -> None:
    repo = _repo(tmp_path)
    spine = build_spine(repo, extractor=FixtureStatementExtractor())
    availability = {status.id: status.available for status in seam_inventory(spine)}
    for stage in SPINE_ORDER:
        assert availability[stage.value] is True
    # The demo and template seams are not part of this pipeline and stay honest.
    assert availability["demo"] is False
    assert availability["template"] is False
    repo.close()


def test_the_whole_chain_runs_and_persists_on_real_code_paths(tmp_path) -> None:
    """quote → candidate → outcome → score → brief → decision → bet → measure.

    Every number is checked against the fixture inputs, computed independently
    of the production renderer, and the chain is re-read from a reopened store.
    """
    path = str(tmp_path / "spine.db")
    repo = build_repository(path)
    service = ODIService(repo)
    job = service.add_job("Onboard customers")
    spine = build_spine(repo, extractor=FixtureStatementExtractor())

    candidates = spine.extractor.extract(QUOTE, quote_id="q1", job_id=job.id)
    proposed = next(c for c in candidates if c.status == "proposed")
    outcome = spine.acceptor.accept(_require_id(proposed), importance=9.0, satisfaction=4.0)
    # 9 + max(9 - 4, 0) = 14, computed here rather than read back from the model.
    assert outcome.opportunity_score == 9.0 + max(9.0 - 4.0, 0.0)

    sample = spine.sampler.sample(outcome.id)
    assert sample.importance == 9.0
    assert sample.satisfaction == 4.0
    assert sample.opportunity_score == 14.0
    assert sample.sample_size is None  # unknown, never a fabricated zero

    brief = spine.brief.render(outcome.id)
    figures = {figure.name: figure.value for figure in brief.figures}
    assert figures["opportunity_score"] == 14.0
    assert figures["decisions"] == 0.0

    decision = spine.decisions.record(
        subject_id=outcome.id, choice="build", rationale="underserved"
    )
    bet = spine.bets.track(
        decision_id=decision.id, statement="activation rises", metric="activation"
    )
    assert bet.baseline is None  # unknown baseline, not a measured zero
    measurement = spine.measurements.measure(bet.id)
    assert measurement.metric == "activation"
    assert measurement.value is None  # nothing measured yet — never invented

    repo.commit()
    repo.close()

    reopened = build_repository(path)
    reloaded_decision = reopened.get_decision(decision.id)
    assert reloaded_decision is not None and reloaded_decision.choice == "build"
    assert reopened.list_bets(decision_id=decision.id)[0].metric == "activation"
    assert reopened.list_measurements(bet_id=bet.id) == []
    reopened.close()


def test_unimplemented_stages_refuse_rather_than_fabricate() -> None:
    """The demo and template seams, which no stage implements, still refuse."""
    from agentic_odi_core.spine import (
        UnavailableDemoLoader,
        UnavailableTemplateEngine,
    )

    with pytest.raises(StageNotImplemented):
        UnavailableDemoLoader().load()
    with pytest.raises(StageNotImplemented):
        UnavailableTemplateEngine().apply("blank")


def test_fixture_extractor_proposals_are_validated_before_storage(tmp_path) -> None:
    """An invalid proposal is retained as rejected with the validator's reason."""
    repo = _repo(tmp_path)
    service = ODIService(repo)
    job = service.add_job("Onboard customers")
    spine = build_spine(
        repo,
        extractor=FixtureStatementExtractor([Proposal(statement=INVALID)]),
    )
    candidates = spine.extractor.extract(INVALID, quote_id="q1", job_id=job.id)
    assert len(candidates) == 1
    stored = repo.get_candidate(candidates[0].candidate_id)
    assert stored.status is CandidateStatus.REJECTED
    assert "Minimize" in stored.rationale
    assert repo.outcomes == {}
    repo.close()
