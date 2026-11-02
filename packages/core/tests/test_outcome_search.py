"""ALH-194 (M2-02.1) — one shared outcome query that the CLI and API both run.

The query is a plain dataclass with no store access; ``search_outcomes`` does
the matching against a repository and returns items, the pre-pagination total,
and per-facet counts computed with that dimension's own filter removed.
"""

from __future__ import annotations

from typing import Any

import pytest
from agentic_odi_core.errors import ValidationError
from agentic_odi_core.query import OutcomeQuery, search_outcomes
from agentic_odi_core.repository import InMemoryRepository
from agentic_odi_core.services import JobNotFoundError, ODIService

JOB = "j-reconcile"


@pytest.fixture
def repo() -> InMemoryRepository:
    from agentic_odi_core.models import Evidence, Job, Outcome, Step, Theme

    store = InMemoryRepository()
    store.add_job(Job(id=JOB, name="Reconcile supplier invoices"))
    store.add_job(Job(id="j-other", name="Another job"))
    store.add_step(
        Step(id="s-1", job_id=JOB, name="Execute the reconciliation", order=4, stage="execute")
    )
    store.add_step(Step(id="s-2", job_id=JOB, name="Locate the invoice", order=2, stage="locate"))
    store.add_outcome(
        Outcome(
            id="o-1",
            job_id=JOB,
            statement="Minimize the time it takes to approve an invoice",
            importance=9,
            satisfaction=2,
            opportunity_score=16.0,
            step_id="s-1",
        )
    )
    store.add_outcome(
        Outcome(
            id="o-2",
            job_id=JOB,
            statement="Avoid mistakes in the amount reconciled",
            importance=7,
            satisfaction=6,
            opportunity_score=8.0,
            step_id="s-2",
        )
    )
    store.add_outcome(
        Outcome(
            id="o-3",
            job_id=JOB,
            statement="Track when the payment actually lands",
            importance=8,
            satisfaction=2,
            opportunity_score=14.0,
        )
    )
    store.add_outcome(
        Outcome(
            id="o-4", job_id="j-other", statement="Reduce the time it takes to onboard a vendor"
        )
    )
    store.add_evidence(
        Evidence(
            id="e-1",
            outcome_id="o-1",
            source_name="interview",
            source_kind="transcript",
            name="q1",
            content="I chase every invoice for days",
        )
    )
    store.add_evidence(
        Evidence(
            id="e-2",
            outcome_id="o-2",
            source_name="interview",
            source_kind="transcript",
            name="q2",
            content="The onboarding notes say it takes three days",
        )
    )
    store.add_evidence(
        Evidence(
            id="e-3",
            outcome_id="o-2",
            source_name="email",
            source_kind="email",
            name="q3",
            content="Three days again, every month",
        )
    )
    store.add_theme(Theme(id="t-1", name="Cash timing", job_id=JOB))
    store.add_theme(Theme(id="t-2", name="Accuracy", job_id=JOB))
    store.outcomes["o-1"].theme_ids = ["t-1"]
    store.outcomes["o-3"].theme_ids = ["t-1"]
    return store


def run(store: InMemoryRepository, limit: int | None = None, offset: int = 0, **kwargs) -> dict:
    return search_outcomes(store, OutcomeQuery(**kwargs), limit, offset)


def ids(result: dict) -> list[str]:
    return [item["id"] for item in result["items"]]


# --- text matching -----------------------------------------------------------


def test_a_blank_query_lists_the_library_biggest_opportunity_first(
    repo: InMemoryRepository,
) -> None:
    result = run(repo)

    assert result["total"] == 4
    assert ids(result) == ["o-1", "o-3", "o-2", "o-4"]


def test_text_matching_is_case_insensitive_across_statements_evidence_and_theme_names(
    repo: InMemoryRepository,
) -> None:
    assert ids(run(repo, text="INVOICE")) == ["o-1"]  # statement and evidence
    assert ids(run(repo, text="three days")) == ["o-2"]  # evidence content only
    assert ids(run(repo, text="cash")) == ["o-1", "o-3"]  # theme name, score order


def test_multiple_matching_evidence_rows_return_the_outcome_once(
    repo: InMemoryRepository,
) -> None:
    result = run(repo, text="three days")

    assert ids(result) == ["o-2"]
    assert result["total"] == 1


# --- filters -------------------------------------------------------------------


def test_stage_filter_matches_the_stage_of_the_outcomes_step(repo: InMemoryRepository) -> None:
    assert ids(run(repo, stage="locate")) == ["o-2"]
    assert ids(run(repo, stage="execute")) == ["o-1"]


def test_theme_ids_are_one_dimension_so_memberships_or_without_duplicating_rows(
    repo: InMemoryRepository,
) -> None:
    result = run(repo, theme_ids=["t-1", "t-2"])

    assert ids(result) == ["o-1", "o-3"]
    assert result["total"] == 2


def test_job_filter_confines_the_search_to_one_job(repo: InMemoryRepository) -> None:
    assert ids(run(repo, job_id=JOB)) == ["o-1", "o-3", "o-2"]
    assert ids(run(repo, job_id="j-other")) == ["o-4"]


def test_confidence_names_whether_a_score_exists_not_what_it_says(
    repo: InMemoryRepository,
) -> None:
    assert sorted(ids(run(repo, confidence="scored"))) == ["o-1", "o-2", "o-3"]
    assert ids(run(repo, confidence="unscored")) == ["o-4"]


def test_the_score_band_is_inclusive_and_excludes_unscored_outcomes(
    repo: InMemoryRepository,
) -> None:
    # o-1 scores 16.0, o-3 14.0, o-2 8.0, o-4 is unscored.
    assert sorted(ids(run(repo, min_score=6))) == ["o-1", "o-2", "o-3"]
    assert ids(run(repo, max_score=6)) == []
    assert sorted(ids(run(repo, min_score=8, max_score=14))) == ["o-2", "o-3"]
    assert ids(run(repo, min_score=0)) == ["o-1", "o-3", "o-2"]


def test_filters_across_dimensions_combine_and_do_not_leak_unrelated_outcomes(
    repo: InMemoryRepository,
) -> None:
    assert ids(run(repo, text="three days", job_id=JOB)) == ["o-2"]
    assert ids(run(repo, text="three days", job_id="j-other")) == []
    assert ids(run(repo, stage="execute", theme_ids=["t-2"])) == []


# --- facets --------------------------------------------------------------------


def test_facets_follow_the_dimension_removed_rule_and_may_overlap_the_total(
    repo: InMemoryRepository,
) -> None:
    result = run(repo)

    # Every stage the job map can hold is counted, so a facet row can grey
    # out the empty ones instead of guessing.
    assert result["facets"]["stage"] == {
        "define": 0,
        "locate": 1,
        "prepare": 0,
        "confirm": 0,
        "execute": 1,
        "monitor": 0,
        "modify": 0,
        "conclude": 0,
    }
    assert result["facets"]["theme"] == {"t-1": 2, "t-2": 0}
    assert result["facets"]["confidence"] == {"scored": 3, "unscored": 1}
    # The theme facet counts overlap (every outcome is also counted under no
    # theme), so they are not forced to add up to the total.
    assert sum(result["facets"]["theme"].values()) != result["total"]


def test_a_facets_own_filter_is_removed_but_the_other_filters_hold(
    repo: InMemoryRepository,
) -> None:
    result = run(repo, theme_ids=["t-1"])

    # The theme row is counted as if no theme were picked, so a second theme
    # can be added from the row itself instead of clearing the first.
    assert result["facets"]["theme"] == {"t-1": 2, "t-2": 0}
    # The other rows keep the theme filter on: clearing stage would only
    # rearrange t-1's own outcomes, and o-2 has no theme to match t-1.
    assert result["facets"]["stage"]["execute"] == 1
    assert result["facets"]["stage"]["locate"] == 0
    # And clearing confidence while t-1 is picked still leaves the two t-1
    # outcomes, both scored — the unscored one has no theme.
    assert result["facets"]["confidence"] == {"scored": 2, "unscored": 0}

    narrowed = run(repo, stage="execute")
    assert narrowed["facets"]["stage"]["execute"] == 1
    # With only the stage filter on, clearing it shows every stage the rest
    # of the library holds — locate included.
    assert narrowed["facets"]["stage"]["locate"] == 1
    assert narrowed["facets"]["theme"] == {"t-1": 1, "t-2": 0}


# --- ordering, pagination, empties --------------------------------------------


def test_results_reuse_the_shared_sort_and_page(repo: InMemoryRepository) -> None:
    first = run(repo, job_id=JOB, limit=2)
    second = run(repo, job_id=JOB, limit=2, offset=2)

    assert first["total"] == 3
    assert ids(first) == ["o-1", "o-3"]
    assert ids(second) == ["o-2"]

    insertion = run(repo, job_id=JOB, sort="insertion")
    assert ids(insertion) == ["o-1", "o-2", "o-3"]


def test_an_impossible_filter_reports_zero_rather_than_everything(
    repo: InMemoryRepository,
) -> None:
    result = run(repo, text="zebra")

    assert result == {"items": [], "total": 0, "facets": result["facets"]}


def test_an_empty_store_says_so_without_inventing_rows() -> None:
    result = search_outcomes(InMemoryRepository(), OutcomeQuery(), None, 0)

    assert result["items"] == []
    assert result["total"] == 0


# --- validation ----------------------------------------------------------------


def test_an_unknown_theme_is_refused_by_name(repo: InMemoryRepository) -> None:
    with pytest.raises(ValidationError, match="no-such-theme"):
        run(repo, theme_ids=["no-such-theme"])


def test_an_unknown_stage_is_refused(repo: InMemoryRepository) -> None:
    with pytest.raises(ValidationError, match="stage"):
        run(repo, stage="sidestep")


def test_an_unknown_confidence_is_refused(repo: InMemoryRepository) -> None:
    with pytest.raises(ValidationError, match="confidence"):
        run(repo, confidence="thick")


def test_an_unknown_sort_is_refused_with_the_permitted_values(
    repo: InMemoryRepository,
) -> None:
    with pytest.raises(ValidationError, match="opportunity_score"):
        run(repo, sort="alphabetical")


def test_tags_are_refused_because_no_outcome_holds_any_yet(
    repo: InMemoryRepository,
) -> None:
    with pytest.raises(ValidationError, match="tags"):
        run(repo, tags=["urgent"])


def test_a_negative_page_is_refused_by_the_shared_page_helper(
    repo: InMemoryRepository,
) -> None:
    with pytest.raises(ValueError, match="offset"):
        run(repo, offset=-1)


def test_search_writes_nothing_to_the_store(repo: InMemoryRepository) -> None:
    before = (
        sorted(repo.outcomes),
        sorted(repo.evidence),
        sorted(repo.signals),
        [o.theme_ids for o in repo.outcomes.values()],
    )

    run(repo, text="invoice", theme_ids=["t-1"], confidence="scored")

    assert (
        sorted(repo.outcomes),
        sorted(repo.evidence),
        sorted(repo.signals),
        [o.theme_ids for o in repo.outcomes.values()],
    ) == before


# --- the service adapter --------------------------------------------------------


@pytest.fixture
def service_repo() -> InMemoryRepository:
    repo = InMemoryRepository()
    service = ODIService(repo)
    job = service.add_job("Reconcile supplier invoices")
    outcome = service.add_outcome(
        job.id, "Minimize the time it takes to approve an invoice", validate_statement=False
    )
    service.add_theme(name="Cash timing", job_id=job.id)
    service.assign_theme([outcome.id], service.list_themes(job_id=job.id)[0].id)
    return repo


def test_the_service_exposes_the_same_result_as_the_raw_query(
    service_repo: InMemoryRepository,
) -> None:
    service = ODIService(service_repo)

    result = service.search_outcomes(text="invoice", stage=None, sort="opportunity_score")

    assert result["total"] == 1
    assert [item["id"] for item in result["items"]] == [
        id_ for id_ in ids(run(service_repo, text="invoice"))
    ]
    assert result["facets"] == run(service_repo, text="invoice")["facets"]


def test_the_service_refuses_an_unknown_job(service_repo: InMemoryRepository) -> None:
    service = ODIService(service_repo)

    with pytest.raises(JobNotFoundError):
        service.search_outcomes(job_id="no-such-job")


def test_the_service_refuses_a_non_numeric_score_bound(service_repo: InMemoryRepository) -> None:
    service = ODIService(service_repo)
    #: JSON callers can hand a bound as prose; the service is the boundary.
    prose_bound: Any = "high"

    with pytest.raises(ValidationError, match="min_score"):
        service.search_outcomes(min_score=prose_bound)
