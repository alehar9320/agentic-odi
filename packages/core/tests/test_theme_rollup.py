"""ALH-163 (M2-01.2) — a theme tree that carries its own counts.

The rollup is a read over memberships that already exist: a parent's number is the **union** of
its own and its children's outcome ids, counted once, and a theme nothing has been filed under
answers with zeroes and an absent top rather than a score nobody measured. Everything here is
decided against the rules the library already ships — ``is_scored`` for measured, ``rank_outcomes``
for the top — so the card, the terminal and the board cannot drift apart.
"""

from __future__ import annotations

import pytest
from agentic_odi_core.models import Theme
from agentic_odi_core.repository import InMemoryRepository, sort_outcomes
from agentic_odi_core.schema import odi_schema
from agentic_odi_core.services import ODIService, ThemeNotFoundError
from agentic_odi_core.theme_tree import ThemeRollup, build_rollup, subtree_ids


@pytest.fixture
def service() -> ODIService:
    svc = ODIService(InMemoryRepository())
    svc.add_job("Reconcile supplier invoices", None)
    return svc


def _job(svc: ODIService) -> str:
    return svc.get_jobs()[0].id


def _outcome(
    svc: ODIService,
    statement: str,
    importance: float | None = None,
    satisfaction: float | None = None,
    job_id: str | None = None,
) -> str:
    return svc.add_outcome(job_id or _job(svc), statement, importance, satisfaction).id


def _file(svc: ODIService, outcome_id: str, *theme_ids: str) -> None:
    for theme_id in theme_ids:
        svc.assign_theme([outcome_id], theme_id)


# --- the count -------------------------------------------------------------------


def test_a_theme_with_nothing_under_it_counts_zero_and_has_no_top(service: ODIService) -> None:
    empty = service.add_theme(name="Cash timing", job_id=_job(service))

    rollup = service.theme_rollup(empty.id)

    assert (rollup.outcomes, rollup.measured) == (0, 0)
    assert rollup.top_opportunity is None
    assert rollup.top_statement is None


def test_an_outcome_in_the_parent_and_two_children_counts_once(service: ODIService) -> None:
    parent = service.add_theme(name="Cash timing", job_id=_job(service))
    left = service.add_theme(name="Payment windows", job_id=_job(service), parent_id=parent.id)
    right = service.add_theme(name="Approval lag", job_id=_job(service), parent_id=parent.id)
    shared = _outcome(
        service,
        "Minimize the time to catch a duplicate charge when the ledger closes twice",
        9.0,
        2.0,
    )
    _file(service, shared, parent.id, left.id, right.id)

    assert service.theme_rollup(parent.id).outcomes == 1
    assert service.theme_rollup(left.id).outcomes == 1
    assert service.theme_rollup(right.id).outcomes == 1


def test_a_parent_rolls_the_union_of_its_children_rather_than_their_sum(
    service: ODIService,
) -> None:
    parent = service.add_theme(name="Cash timing", job_id=_job(service))
    left = service.add_theme(name="Payment windows", job_id=_job(service), parent_id=parent.id)
    right = service.add_theme(name="Approval lag", job_id=_job(service), parent_id=parent.id)
    direct = _outcome(
        service, "Minimize the number of ledgers closed by hand when two feeds agree", 6.0, 6.0
    )
    in_left = _outcome(
        service, "Maximize the percentage of duplicates caught when an invoice is scanned", 7.0, 1.0
    )
    in_both = _outcome(
        service, "Minimize the time to trace a charge when a bank feed is late", 8.0, 4.0
    )
    in_right = _outcome(
        service, "Minimize the steps to approve a waiver when a credit note is issued", 5.0, 5.0
    )
    _file(service, direct, parent.id)
    _file(service, in_left, left.id)
    _file(service, in_both, left.id, right.id)
    _file(service, in_right, right.id)

    rollup = service.theme_rollup(parent.id)

    # 1 + 2 + 2 memberships, four outcomes: the union is what a person reads, not the sum.
    assert rollup.outcomes == 4
    assert service.theme_rollup(left.id).outcomes + service.theme_rollup(right.id).outcomes == 4


def test_the_rollup_names_the_theme_it_was_read_for(service: ODIService) -> None:
    parent = service.add_theme(name="Cash timing", job_id=_job(service))
    child = service.add_theme(name="Payment windows", job_id=_job(service), parent_id=parent.id)

    assert service.theme_rollup(child.id).parent_id == parent.id
    assert service.theme_rollup(child.id).name == "Payment windows"


# --- measured, and the top --------------------------------------------------------


def test_measured_counts_only_outcomes_with_both_scores(service: ODIService) -> None:
    theme = service.add_theme(name="Cash timing", job_id=_job(service))
    _file(
        service,
        _outcome(service, "Minimize the cost of a stale ledger when two feeds disagree", 8.0, 2.0),
        theme.id,
    )
    _file(
        service,
        _outcome(service, "Minimize the time to reconcile a refund when it is issued", None, None),
        theme.id,
    )
    _file(
        service,
        _outcome(
            service, "Minimize the number of split charges when a payer uses two cards", 7.0, None
        ),
        theme.id,
    )

    rollup = service.theme_rollup(theme.id)

    assert (rollup.outcomes, rollup.measured) == (3, 1)


def test_measured_is_the_same_rule_the_search_facet_uses(service: ODIService) -> None:
    parent = service.add_theme(name="Cash timing", job_id=_job(service))
    child = service.add_theme(name="Payment windows", job_id=_job(service), parent_id=parent.id)
    _file(
        service,
        _outcome(service, "Minimize the cost of a stale ledger when two feeds disagree", 8.0, 2.0),
        parent.id,
    )
    _file(
        service,
        _outcome(service, "Minimize the time to reconcile a refund when it is issued", 3.0, 9.0),
        child.id,
    )
    _file(
        service,
        _outcome(service, "Minimize the number of split charges when a payer uses two cards"),
        child.id,
    )

    rollup = service.theme_rollup(parent.id)
    found = service.search_outcomes(theme_ids=subtree_ids(service.repo.themes, parent.id))

    assert rollup.measured == found["facets"]["confidence"]["scored"]
    assert rollup.outcomes == found["total"]


def test_the_top_is_the_best_scored_outcome_anywhere_in_the_subtree(service: ODIService) -> None:
    parent = service.add_theme(name="Cash timing", job_id=_job(service))
    child = service.add_theme(name="Payment windows", job_id=_job(service), parent_id=parent.id)
    best = "Minimize the time to catch a duplicate before a ledger is closed"
    _file(
        service,
        _outcome(service, "Minimize the time to reconcile a refund when it is issued", 2.0, 2.0),
        parent.id,
    )
    _file(service, _outcome(service, best, 9.0, 1.0), child.id)

    rollup = service.theme_rollup(parent.id)

    assert rollup.top_statement == best
    assert rollup.top_opportunity == 9.0 + max(9.0 - 1.0, 0.0)


def test_an_equal_top_resolves_the_way_the_library_sorts(service: ODIService) -> None:
    theme = service.add_theme(name="Cash timing", job_id=_job(service))
    first = _outcome(service, "Minimize the time to reconcile a refund when it is issued", 6.0, 2.0)
    second = _outcome(
        service, "Minimize the time to catch a duplicate before a ledger is closed", 6.0, 2.0
    )
    _file(service, first, theme.id)
    _file(service, second, theme.id)

    included = [o for o in (service.get_outcome(first), service.get_outcome(second)) if o]
    expected = sort_outcomes(included, "opportunity_score")[0]
    rollup = service.theme_rollup(theme.id)

    assert rollup.top_statement == expected.statement


def test_a_theme_of_unscored_outcomes_reports_nothing_measured_rather_than_zero(
    service: ODIService,
) -> None:
    theme = service.add_theme(name="Cash timing", job_id=_job(service))
    _file(
        service,
        _outcome(service, "Minimize the time to reconcile a refund when it is issued"),
        theme.id,
    )
    _file(
        service,
        _outcome(service, "Minimize the cost of a duplicate charge before a ledger is closed"),
        theme.id,
    )

    rollup = service.theme_rollup(theme.id)

    assert rollup.outcomes == 2
    assert rollup.measured == 0
    assert rollup.top_opportunity is None
    assert rollup.top_statement is None


# --- the walk ---------------------------------------------------------------------


def test_the_walk_stops_at_the_second_level_even_if_a_third_was_stored(
    service: ODIService,
) -> None:
    parent = service.add_theme(name="Cash timing", job_id=_job(service))
    child = service.add_theme(name="Payment windows", job_id=_job(service), parent_id=parent.id)
    grandchild = Theme(id="t-grand", name="Bank feeds", job_id=_job(service), parent_id=child.id)
    service.repo.add_theme(grandchild)
    inside = _outcome(
        service, "Minimize the time to reconcile a refund when it is issued", 9.0, 1.0
    )
    _file(service, inside, grandchild.id)

    assert subtree_ids(service.repo.themes, parent.id) == [parent.id, child.id]
    assert service.theme_rollup(parent.id).outcomes == 0


def test_a_parent_chain_that_cycles_returns_instead_of_spinning(service: ODIService) -> None:
    left = Theme(id="t-left", name="Cash timing", job_id=_job(service), parent_id="t-right")
    right = Theme(id="t-right", name="Payment windows", job_id=_job(service), parent_id="t-left")
    service.repo.add_theme(left)
    service.repo.add_theme(right)
    inside = _outcome(
        service, "Minimize the time to reconcile a refund when it is issued", 9.0, 1.0
    )
    _file(service, inside, right.id)

    assert subtree_ids(service.repo.themes, left.id) == [left.id, right.id]
    assert service.theme_rollup(left.id).outcomes == 1


def test_a_deleted_child_stops_counting_toward_its_parent(service: ODIService) -> None:
    parent = service.add_theme(name="Cash timing", job_id=_job(service))
    child = service.add_theme(name="Payment windows", job_id=_job(service), parent_id=parent.id)
    only_child = _outcome(
        service, "Minimize the time to reconcile a refund when it is issued", 9.0, 1.0
    )
    also_parent = _outcome(
        service, "Minimize the cost of a duplicate charge before a ledger is closed", 4.0, 4.0
    )
    _file(service, only_child, child.id)
    _file(service, also_parent, child.id, parent.id)

    service.delete_theme(child.id)

    rollup = service.theme_rollup(parent.id)
    assert rollup.outcomes == 1
    assert rollup.measured == 1
    assert (
        rollup.top_statement == "Minimize the cost of a duplicate charge before a ledger is closed"
    )


def test_a_workspace_theme_counts_outcomes_from_any_job(service: ODIService) -> None:
    other = service.add_job("Onboard a hospital unit", None).id
    theme = service.add_theme(name="Waiting on someone else")
    _file(
        service,
        _outcome(service, "Minimize the time to reconcile a refund when it is issued", 9.0, 1.0),
        theme.id,
    )
    _file(
        service,
        _outcome(
            service,
            "Minimize the time to find an empty bed before a ward fills",
            8.0,
            2.0,
            job_id=other,
        ),
        theme.id,
    )

    assert service.theme_rollup(theme.id).outcomes == 2


# --- listing the tree -------------------------------------------------------------


def test_listing_orders_parents_before_their_children(service: ODIService) -> None:
    service.add_theme(name="Beta", job_id=_job(service), ordinal=1)
    alpha = service.add_theme(name="Alpha", job_id=_job(service), ordinal=0)
    service.add_theme(name="Under alpha", job_id=_job(service), parent_id=alpha.id, ordinal=0)

    names = [rollup.name for rollup in service.list_theme_rollups(_job(service))]

    assert names == ["Alpha", "Under alpha", "Beta"]


def test_listing_the_scope_counts_every_theme_once(service: ODIService) -> None:
    parent = service.add_theme(name="Cash timing", job_id=_job(service))
    child = service.add_theme(name="Payment windows", job_id=_job(service), parent_id=parent.id)
    inside = _outcome(
        service, "Minimize the time to reconcile a refund when it is issued", 9.0, 1.0
    )
    _file(service, inside, parent.id, child.id)

    listed = {rollup.theme_id: rollup.outcomes for rollup in service.list_theme_rollups()}

    assert listed == {parent.id: 1, child.id: 1}


# --- failure, and what a read must never do ---------------------------------------


def test_an_unknown_theme_is_a_not_found_rather_than_an_empty_rollup(service: ODIService) -> None:
    with pytest.raises(ThemeNotFoundError) as refused:
        service.theme_rollup("t-ghost")

    assert "t-ghost" in str(refused.value)


def test_reading_the_rollup_twice_writes_nothing(service: ODIService) -> None:
    theme = service.add_theme(name="Cash timing", job_id=_job(service))
    _file(
        service,
        _outcome(service, "Minimize the time to reconcile a refund when it is issued", 9.0, 1.0),
        theme.id,
    )
    before = _snapshot(service)
    writes = _watch_writes(service)

    first = service.theme_rollup(theme.id)
    second = service.list_theme_rollups()

    assert first == service.theme_rollup(theme.id)
    assert [rollup.theme_id for rollup in second] == [theme.id]
    assert writes.calls == []
    assert _snapshot(service) == before


def test_the_rollup_is_a_read_result_and_not_a_published_entity(service: ODIService) -> None:
    theme = service.add_theme(name="Cash timing", job_id=_job(service))

    rollup = service.theme_rollup(theme.id)

    assert isinstance(rollup, ThemeRollup)
    assert set(rollup.as_dict()) == {
        "theme_id",
        "name",
        "parent_id",
        "outcomes",
        "measured",
        "top_opportunity",
        "top_statement",
    }
    assert "ThemeRollup" not in odi_schema()


def test_the_rollup_counts_what_the_store_holds_rather_than_what_a_membership_says(
    service: ODIService,
) -> None:
    theme = service.add_theme(name="Cash timing", job_id=_job(service))
    inside = _outcome(
        service, "Minimize the time to reconcile a refund when it is issued", 9.0, 1.0
    )
    _file(service, inside, theme.id)

    service.delete_outcome(inside)

    assert service.theme_rollup(theme.id).outcomes == 0


def test_build_rollup_is_a_fold_over_the_models_it_is_given(service: ODIService) -> None:
    theme = service.add_theme(name="Cash timing", job_id=_job(service))
    inside = _outcome(
        service, "Minimize the time to reconcile a refund when it is issued", 9.0, 1.0
    )
    _file(service, inside, theme.id)

    rollup = build_rollup(theme, service.repo.themes, service.repo.outcomes.values())

    assert rollup == service.theme_rollup(theme.id)


# --- helpers ----------------------------------------------------------------------


def _snapshot(service: ODIService) -> tuple[object, ...]:
    return (
        tuple(theme.model_dump() for theme in service.repo.themes.values()),
        tuple(outcome.model_dump() for outcome in service.repo.outcomes.values()),
    )


class _WriteSpy:
    def __init__(self) -> None:
        self.calls: list[str] = []


def _watch_writes(service: ODIService) -> _WriteSpy:
    """Count every call that could file, rename or score something."""
    spy = _WriteSpy()
    for name in (
        "add_theme",
        "update_theme",
        "delete_theme",
        "change_theme_membership",
        "add_outcome",
        "update_outcome",
        "delete_outcome",
    ):
        original = getattr(service.repo, name, None)
        if original is None:
            continue

        def make(field: str, target: object) -> object:
            def wrapper(*args: object, **kwargs: object) -> object:
                spy.calls.append(field)
                return target(*args, **kwargs)  # type: ignore[operator]

            return wrapper

        setattr(service.repo, name, make(name, original))
    return spy
