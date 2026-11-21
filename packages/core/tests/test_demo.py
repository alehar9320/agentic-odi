"""The demo workspace loads on purpose, and never masquerades as real data.

These tests pin the promises that make the sample safe: the exact counts, a
second load is a no-op, loading is additive, and the fixture claims no entity
the store cannot hold.
"""

from __future__ import annotations

from pathlib import Path

from agentic_odi_core.demo import (
    DEMO_JOB_ID,
    demo_evidence,
    demo_job,
    demo_outcomes,
    demo_steps,
    load_demo,
)
from agentic_odi_core.factory import build_repository


def test_the_fixture_has_the_declared_counts() -> None:
    assert len(demo_steps()) == 8
    assert len(demo_outcomes()) == 40
    assert len(demo_evidence()) == 12


def test_every_fixture_row_is_labelled_demo() -> None:
    rows = [demo_job(), *demo_steps(), *demo_outcomes(), *demo_evidence()]
    assert all(row.origin == "demo" for row in rows)  # type: ignore[attr-defined]


def test_the_fixture_ids_are_deterministic() -> None:
    assert demo_job().id == DEMO_JOB_ID
    assert [s.id for s in demo_steps()] == [f"demo-step-{i}" for i in range(1, 9)]
    assert demo_outcomes()[0].id == "demo-outcome-1"


def test_the_fixture_claims_no_entity_the_store_cannot_hold() -> None:
    # Segments, decisions and bets arrive with M1; the fixture must not invent
    # them ahead of the loop that would produce them.
    import inspect

    from agentic_odi_core import demo as demo_module

    source = inspect.getsource(demo_module)
    assert "DecisionRecord(" not in source
    assert "BetRecord(" not in source
    assert "MeasurementRecord(" not in source


def test_loading_fills_a_store_with_the_exact_counts(tmp_path: Path) -> None:
    repo = build_repository(str(tmp_path / "demo.db"))
    result = load_demo(repo)
    assert (result.jobs, result.steps, result.outcomes, result.evidence) == (1, 8, 40, 12)
    assert len(repo.jobs) == 1
    assert len(repo.steps) == 8
    assert len(repo.outcomes) == 40
    assert len(repo.evidence) == 12
    repo.close()


def test_loading_twice_leaves_the_counts_unchanged(tmp_path: Path) -> None:
    repo = build_repository(str(tmp_path / "demo.db"))
    load_demo(repo)
    load_demo(repo)
    assert (len(repo.jobs), len(repo.steps), len(repo.outcomes), len(repo.evidence)) == (
        1,
        8,
        40,
        12,
    )
    repo.close()


def test_loading_is_additive_and_leaves_user_rows_intact(tmp_path: Path) -> None:
    from agentic_odi_core import ODIService

    repo = build_repository(str(tmp_path / "demo.db"))
    service = ODIService(repo)
    user_job = service.add_job("A real job")
    service.add_outcome(
        user_job.id,
        "Minimize the time it takes to ship when a release is cut.",
        importance=8.0,
        satisfaction=3.0,
    )
    load_demo(repo)
    reloaded = repo.get_job(user_job.id)
    assert reloaded is not None
    assert reloaded.origin == "user"
    assert len(repo.jobs) == 2  # the user's job plus the demo's, not replaced
    repo.close()


def test_every_demo_outcome_is_a_valid_odi_statement(tmp_path: Path) -> None:
    from agentic_odi_core.evaluation import evaluate_outcome_statement

    for outcome in demo_outcomes():
        assert evaluate_outcome_statement(outcome.statement)["valid"], outcome.statement
