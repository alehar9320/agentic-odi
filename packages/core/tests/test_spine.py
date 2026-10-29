"""The spine seam refuses rather than fabricating, and reports its gaps.

These tests pin the two promises that make the seam safe to depend on before the
stages exist:

1. a stub raises :class:`StageNotImplemented` — it never returns a placeholder
   that a caller could mistake for a real number, and
2. the inventory says "nothing yet" honestly, naming the issue that owns each
   gap instead of hiding it.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest
from agentic_odi_core.models import Outcome
from agentic_odi_core.spine import (
    DEMO_SEAM,
    SEAM_OWNERS,
    SPINE_ORDER,
    TEMPLATE_SEAM,
    Bet,
    BriefDocument,
    BriefFigure,
    CandidateOutcome,
    Decision,
    DemoWorkspace,
    Measurement,
    ScoreSample,
    SeamStatus,
    Spine,
    SpineStage,
    StageNotImplemented,
    UnavailableBetTracker,
    UnavailableBriefRenderer,
    UnavailableCandidateExtractor,
    UnavailableDecisionRecorder,
    UnavailableDemoLoader,
    UnavailableMeasurementReader,
    UnavailableOutcomeAcceptor,
    UnavailableScoreSampler,
    UnavailableTemplateEngine,
    default_spine,
    missing_stages,
    seam_inventory,
    seam_status,
    spine_summary,
)

# --------------------------------------------------------------------------- #
# The stages and their owners
# --------------------------------------------------------------------------- #


def test_the_pipeline_has_the_seven_stages_in_order() -> None:
    assert [stage.value for stage in SPINE_ORDER] == [
        "candidate",
        "outcome",
        "score",
        "brief",
        "decision",
        "bet",
        "measure",
    ]


def test_every_stage_has_an_owner_that_names_an_issue() -> None:
    for stage in SPINE_ORDER:
        owner = SEAM_OWNERS[stage.value]
        assert owner.issue.startswith("ALH-")
        assert owner.title
        assert owner.issue_title


def test_only_the_named_module_is_claimed() -> None:
    # The seam only records a file where an issue names one; guessing the rest
    # would be fabrication of a different kind.
    modules = {owner.id: owner.module for owner in SEAM_OWNERS.values()}
    assert modules["brief"] == "brief.py"
    assert modules["candidate"] is None
    assert modules["decision"] is None


def test_the_demo_and_template_seams_have_owners() -> None:
    assert SEAM_OWNERS[DEMO_SEAM].issue == "ALH-58"
    assert SEAM_OWNERS[TEMPLATE_SEAM].issue == "ALH-119"


# --------------------------------------------------------------------------- #
# Stubs refuse rather than fabricate
# --------------------------------------------------------------------------- #


def test_the_default_spine_is_entirely_stubbed() -> None:
    spine = default_spine()
    for stage in SPINE_ORDER:
        assert isinstance(spine.stage(stage), _STUB_TYPES_BY_STAGE[stage])


_STUB_TYPES_BY_STAGE: dict[SpineStage, type] = {
    SpineStage.CANDIDATE: UnavailableCandidateExtractor,
    SpineStage.OUTCOME: UnavailableOutcomeAcceptor,
    SpineStage.SCORE: UnavailableScoreSampler,
    SpineStage.BRIEF: UnavailableBriefRenderer,
    SpineStage.DECISION: UnavailableDecisionRecorder,
    SpineStage.BET: UnavailableBetTracker,
    SpineStage.MEASURE: UnavailableMeasurementReader,
}


@pytest.mark.parametrize(
    ("call", "seam_id"),
    [
        (
            lambda s: s.extractor.extract("a quote", quote_id="q", job_id="j"),
            "candidate",
        ),
        (
            lambda s: s.acceptor.accept("candidate-1", importance=5.0, satisfaction=5.0),
            "outcome",
        ),
        (lambda s: s.sampler.sample("o"), "score"),
        (lambda s: s.brief.render("subject"), "brief"),
        (lambda s: s.decisions.record(subject_id="s", choice="c", rationale="r"), "decision"),
        (lambda s: s.bets.track(decision_id="d", statement="s", metric="m"), "bet"),
        (lambda s: s.measurements.measure("b"), "measure"),
    ],
)
def test_each_stub_raises_stage_not_implemented(call, seam_id: str) -> None:
    with pytest.raises(StageNotImplemented) as caught:
        call(default_spine())
    assert caught.value.seam_id == seam_id


def test_the_refusal_names_the_owning_issue() -> None:
    with pytest.raises(StageNotImplemented) as caught:
        default_spine().extractor.extract("a quote", quote_id="q", job_id="j")
    message = str(caught.value)
    assert "ALH-17" in message
    assert "not implemented" in message


def test_the_demo_loader_stub_refuses() -> None:
    with pytest.raises(StageNotImplemented) as caught:
        UnavailableDemoLoader().load()
    assert caught.value.seam_id == DEMO_SEAM


def test_the_template_engine_stub_refuses() -> None:
    with pytest.raises(StageNotImplemented) as caught:
        UnavailableTemplateEngine().apply("blank")
    assert caught.value.seam_id == TEMPLATE_SEAM


def test_a_refusal_is_an_odi_error() -> None:
    # Surfaces already catch OdiError; the refusal must not escape that net and
    # surface as an unhandled crash that a caller might paper over.
    from agentic_odi_core.errors import OdiError

    assert issubclass(StageNotImplemented, OdiError)


# --------------------------------------------------------------------------- #
# The inventory says "nothing yet" honestly
# --------------------------------------------------------------------------- #


def test_the_default_inventory_reports_every_seam_missing() -> None:
    inventory = seam_inventory()
    assert [status.id for status in inventory] == [
        *(stage.value for stage in SPINE_ORDER),
        DEMO_SEAM,
        TEMPLATE_SEAM,
    ]
    assert all(not status.available for status in inventory)


def test_missing_stages_lists_every_gap_in_order() -> None:
    assert missing_stages() == [
        *(stage.value for stage in SPINE_ORDER),
        DEMO_SEAM,
        TEMPLATE_SEAM,
    ]


def test_wiring_a_real_stage_marks_only_that_stage_available() -> None:
    class RealExtractor:
        def extract(
            self, quote: str, *, quote_id: str, job_id: str, **kwargs: object
        ) -> list[CandidateOutcome]:
            return []

    spine = Spine(extractor=RealExtractor())
    statuses = {status.id: status for status in seam_inventory(spine)}
    assert statuses["candidate"].available is True
    assert statuses["outcome"].available is False


def test_wiring_a_demo_loader_marks_the_demo_seam_available() -> None:
    class RealDemoLoader:
        def load(self, *, name: str = "demo") -> DemoWorkspace:
            return DemoWorkspace(name=name)

    statuses = {status.id: status for status in seam_inventory(demo=RealDemoLoader())}
    assert statuses[DEMO_SEAM].available is True


def test_wiring_a_template_engine_marks_the_template_seam_available() -> None:
    class RealTemplateEngine:
        def apply(self, template_id: str) -> DemoWorkspace:
            return DemoWorkspace(name=template_id)

    statuses = {status.id: status for status in seam_inventory(templates=RealTemplateEngine())}
    assert statuses[TEMPLATE_SEAM].available is True


def test_a_seam_status_carries_its_owner() -> None:
    status = seam_status("brief", None)
    assert isinstance(status, SeamStatus)
    assert status.owner.issue == "ALH-32"


def test_the_summary_says_nothing_is_implemented_and_names_each_gap() -> None:
    summary = spine_summary()
    assert "0 of 7 are implemented" in summary
    for stage in SPINE_ORDER:
        assert f"- {stage.value}: not implemented yet" in summary
    assert "ALH-17" in summary  # candidate
    assert "ALH-32" in summary  # brief
    assert "ALH-47" in summary  # measure


def test_the_summary_prints_no_fabricated_number() -> None:
    # "0 of 7" is a count of stages, not a claimed ODI result. No other digit
    # may appear, because any other number would be invented.
    summary = spine_summary()
    assert "0 of 7" in summary
    assert summary.count("0 of 7") == 1


def test_the_summary_reports_a_wired_stage_as_available() -> None:
    class RealBriefRenderer:
        def render(self, subject_id: str) -> BriefDocument:
            return BriefDocument(subject_id=subject_id, headline="")

    summary = spine_summary(Spine(brief=RealBriefRenderer()))
    assert "1 of 7 are implemented" in summary
    assert "- brief: available" in summary


# --------------------------------------------------------------------------- #
# The wire shapes stay honest about missing data
# --------------------------------------------------------------------------- #


def test_a_score_sample_without_both_scores_has_no_opportunity_score() -> None:
    assert ScoreSample(outcome_id="o").opportunity_score is None
    assert ScoreSample(outcome_id="o", importance=7.0).opportunity_score is None


def test_a_score_sample_computes_the_opportunity_score() -> None:
    sample = ScoreSample(outcome_id="o", importance=9.0, satisfaction=3.0, sample_size=12)
    assert sample.opportunity_score == pytest.approx(15.0)
    assert sample.sample_size == 12


def test_an_unknown_sample_size_is_not_zero() -> None:
    # An unmeasured sample is unknown, not zero responses.
    assert ScoreSample(outcome_id="o").sample_size is None


def test_a_brief_figure_always_carries_its_basis() -> None:
    figure = BriefFigure(name="outcomes", value=12.0, basis="12 accepted outcomes")
    assert figure.basis


def test_a_measurement_may_be_missing_its_value() -> None:
    # "nothing yet" must be representable without inventing a number.
    measurement = Measurement(bet_id="b", metric="activation", value=None, observed_at="2026-10-29")
    assert measurement.value is None


def test_a_demo_workspace_is_labelled_as_sample_data() -> None:
    assert DemoWorkspace(name="demo").labelled is True


def test_the_wire_shapes_are_not_persisted_entities() -> None:
    # The seam's shapes must not leak into the persisted schema; when a stage
    # lands it introduces its real model and the persistence checklist with it.
    from agentic_odi_core.schema import odi_schema

    schema_names = set(odi_schema())
    for wire_type in (CandidateOutcome, ScoreSample, BriefFigure, BriefDocument):
        assert wire_type.__name__ not in schema_names


def test_the_decision_and_bet_shapes_are_frozen() -> None:
    decision = Decision(
        id="d", subject_id="s", choice="ship", rationale="because", decided_at="2026-10-29"
    )
    bet = Bet(id="b", decision_id="d", statement="it moves", metric="activation")
    with pytest.raises(FrozenInstanceError):
        decision.choice = "other"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        bet.metric = "other"  # type: ignore[misc]


# --------------------------------------------------------------------------- #
# The seam composes: the seven stages chain through one object
# --------------------------------------------------------------------------- #


def test_the_seam_composes_across_all_seven_stages() -> None:
    """The protocols chain quote → candidate → outcome → score → brief →
    decision → bet → measure.

    Every stage here is a labelled test double defined in this test, not a
    shipped implementation: the point is that the *seam* composes, so the real
    stages can be dropped in one at a time. The doubles carry no fabricated ODI
    claim into any surface — they exist only to prove the interfaces fit.
    """

    class FakeExtractor:
        def extract(
            self, quote: str, *, quote_id: str, job_id: str, **kwargs: object
        ) -> list[CandidateOutcome]:
            return [
                CandidateOutcome(
                    quote_id=quote_id,
                    statement="Minimize time",
                    source_quote=quote,
                    candidate_id="c1",
                )
            ]

    class FakeAcceptor:
        def accept(
            self, candidate_id: str, *, importance: float, satisfaction: float, **kwargs: object
        ) -> Outcome:
            return Outcome(
                id="o1",
                job_id="job1",
                statement="Minimize time",
                importance=importance,
                satisfaction=satisfaction,
            )

    class FakeSampler:
        def sample(self, outcome_id: str) -> ScoreSample:
            return ScoreSample(
                outcome_id=outcome_id, importance=9.0, satisfaction=3.0, sample_size=12
            )

    class FakeBrief:
        def render(self, subject_id: str) -> BriefDocument:
            return BriefDocument(
                subject_id=subject_id,
                headline="one outcome",
                figures=(BriefFigure(name="outcomes", value=1.0, basis="1 accepted outcome"),),
            )

    class FakeDecisions:
        def record(self, *, subject_id: str, choice: str, rationale: str) -> Decision:
            return Decision(
                id="d1",
                subject_id=subject_id,
                choice=choice,
                rationale=rationale,
                decided_at="2026-10-29",
            )

    class FakeBets:
        def track(self, *, decision_id: str, statement: str, metric: str) -> Bet:
            return Bet(id="b1", decision_id=decision_id, statement=statement, metric=metric)

    class FakeMeasurements:
        def measure(self, bet_id: str) -> Measurement:
            return Measurement(
                bet_id=bet_id, metric="activation", value=None, observed_at="2026-10-29"
            )

    spine = Spine(
        extractor=FakeExtractor(),
        acceptor=FakeAcceptor(),
        sampler=FakeSampler(),
        brief=FakeBrief(),
        decisions=FakeDecisions(),
        bets=FakeBets(),
        measurements=FakeMeasurements(),
    )

    candidate = spine.extractor.extract(
        "Customers say onboarding takes too long.", quote_id="q1", job_id="job1"
    )[0]
    assert candidate.candidate_id is not None
    outcome = spine.acceptor.accept(candidate.candidate_id, importance=9.0, satisfaction=3.0)
    score = spine.sampler.sample(outcome.id)
    brief = spine.brief.render(outcome.id)
    decision = spine.decisions.record(
        subject_id=outcome.id, choice="ship", rationale="highest score"
    )
    bet = spine.bets.track(
        decision_id=decision.id, statement="activation rises", metric="activation"
    )
    measurement = spine.measurements.measure(bet.id)

    # The chain carries the same subject through every hop.
    assert outcome.job_id == "job1"
    assert score.outcome_id == outcome.id
    assert brief.subject_id == outcome.id
    assert decision.subject_id == outcome.id
    assert bet.decision_id == decision.id
    assert measurement.bet_id == bet.id
    # A missing measurement stays missing rather than becoming zero.
    assert measurement.value is None
    # With every pipeline stage wired, the inventory reports the whole pipeline
    # available. (The demo and template seams are off-pipeline and stay unwired.)
    pipeline_missing = [
        status.id
        for status in seam_inventory(spine)
        if status.id in {stage.value for stage in SPINE_ORDER} and not status.available
    ]
    assert pipeline_missing == []
