"""ALH-65 (M2-01) — themes group outcomes into a named two-level tree."""

from __future__ import annotations

import pytest
from agentic_odi_core.errors import ValidationError
from agentic_odi_core.models import Outcome
from agentic_odi_core.repository import InMemoryRepository
from agentic_odi_core.schema import odi_schema
from agentic_odi_core.services import ODIService
from pydantic import ValidationError as PydanticValidationError

# --- the model ---------------------------------------------------------------


def theme(**kwargs):
    from agentic_odi_core.models import Theme

    return Theme(**{"name": "Getting paid", **kwargs})


def test_a_theme_carries_its_place_in_the_tree_by_default() -> None:
    theme_model = theme()

    assert theme_model.job_id is None
    assert theme_model.parent_id is None
    assert theme_model.description is None
    assert theme_model.ordinal == 0


def test_an_outcome_belongs_to_no_themes_until_one_is_assigned() -> None:
    outcome = Outcome(id="o-1", job_id="j-1", statement="Track when payment lands")

    assert outcome.theme_ids == []


def test_a_theme_cannot_be_its_own_parent() -> None:
    from agentic_odi_core.models import Theme

    with pytest.raises(PydanticValidationError):
        Theme(id="t-1", name="Loop", parent_id="t-1")


def test_theme_is_a_published_entity_schema() -> None:
    schema = odi_schema()

    assert "Theme" in schema
    assert "theme_ids" in schema["Outcome"]["properties"]


# --- the service: adding, listing, renaming ----------------------------------


@pytest.fixture
def service() -> ODIService:
    svc = ODIService(InMemoryRepository())
    svc.add_job("Reconcile supplier invoices", None)
    return svc


def _job_id(service: ODIService) -> str:
    return service.get_jobs()[0].id


def test_list_themes_is_empty_before_any_theme_exists(service: ODIService) -> None:
    assert service.list_themes() == []


def test_add_theme_returns_a_planned_named_theme(service: ODIService) -> None:
    created = service.add_theme(name="Cash timing", description="When money actually moves")

    stored = service.get_theme(created.id)

    assert stored == created
    assert stored.name == "Cash timing"
    assert service.list_themes() == [created]


def test_a_child_theme_lives_under_its_parent(service: ODIService) -> None:
    parent = service.add_theme(name="Cash timing")
    child = service.add_theme(name="Payment windows", parent_id=parent.id)

    assert child.parent_id == parent.id


def test_rename_theme_changes_the_label_and_keeps_the_tree(service: ODIService) -> None:
    parent = service.add_theme(name="Cash timing")
    child = service.add_theme(name="Payment windows", parent_id=parent.id)

    renamed = service.rename_theme(parent.id, name="Money movement")

    assert renamed.name == "Money movement"
    assert service.get_theme(child.id).parent_id == parent.id


def test_renaming_a_missing_theme_fails(service: ODIService) -> None:
    from agentic_odi_core.services import ThemeNotFoundError

    with pytest.raises(ThemeNotFoundError):
        service.rename_theme("nope", name="Anything")


# --- the service: depth and parent validation --------------------------------


def test_a_third_level_theme_is_refused_naming_the_limit(service: ODIService) -> None:
    top = service.add_theme(name="Top")
    middle = service.add_theme(name="Middle", parent_id=top.id)

    with pytest.raises(ValidationError, match="two levels"):
        service.add_theme(name="Leaf", parent_id=middle.id)

    assert service.get_theme(middle.id).parent_id == top.id


def test_a_theme_under_a_missing_parent_is_refused(service: ODIService) -> None:
    with pytest.raises(ValidationError):
        service.add_theme(name="Orphan", parent_id="no-such-theme")


def test_a_theme_under_a_foreign_job_parent_is_refused(service: ODIService) -> None:
    parent = service.add_theme(name="Job one", job_id=_job_id(service))

    with pytest.raises(ValidationError):
        service.add_theme(name="Job two", parent_id=parent.id)

    assert service.list_themes() == [parent]


def test_reparenting_a_theme_deeper_than_the_limit_is_refused(service: ODIService) -> None:
    top = service.add_theme(name="Top")
    service.add_theme(name="Child of top", parent_id=top.id)
    other_top = service.add_theme(name="Other top")

    with pytest.raises(ValidationError, match="two levels"):
        service.rename_theme(top.id, parent_id=other_top.id)

    assert service.get_theme(top.id).parent_id is None


# --- the service: membership --------------------------------------------------


def _outcome(service: ODIService, job_id: str, statement: str) -> str:
    created = service.add_outcome(job_id, statement=statement, importance=8, satisfaction=2)
    return created.id


def test_assign_theme_files_the_outcome(service: ODIService) -> None:
    job_id = _job_id(service)
    outcome_id = _outcome(
        service, job_id, "Minimize the time it takes to find a payment when reconciling"
    )
    theme = service.add_theme(name="Cash timing", job_id=job_id)

    updated = service.assign_theme([outcome_id], theme.id)

    assert updated[0].theme_ids == [theme.id]
    stored = service.repo.get_outcome(outcome_id)
    assert stored is not None and stored.theme_ids == [theme.id]


def test_an_outcome_joins_a_workspace_theme_of_any_job(service: ODIService) -> None:
    service.add_job("Onboard a supplier", None)
    other_id = service.get_jobs()[1].id
    outcome_id = _outcome(
        service, other_id, "Minimize the time it takes to approve access when a supplier joins"
    )
    workspace_theme = service.add_theme(name="Cross-job: waiting")

    updated = service.assign_theme([outcome_id], workspace_theme.id)

    assert updated[0].theme_ids == [workspace_theme.id]


def test_assigning_a_foreign_job_outcome_is_refused_without_mutation(service: ODIService) -> None:
    job_id = _job_id(service)
    other = service.add_job("Onboard a supplier", None)
    outcome_id = _outcome(
        service, other.id, "Minimize the time it takes to approve access when a supplier joins"
    )
    theme = service.add_theme(name="Cash timing", job_id=job_id)

    with pytest.raises(ValidationError):
        service.assign_theme([outcome_id], theme.id)

    stored = service.repo.get_outcome(outcome_id)
    assert stored is not None and stored.theme_ids == []


def test_assigning_one_missing_outcome_refuses_the_whole_call(service: ODIService) -> None:
    from agentic_odi_core.services import OutcomeNotFoundError

    job_id = _job_id(service)
    outcome_id = _outcome(
        service, job_id, "Minimize the time it takes to find a payment when reconciling"
    )
    theme = service.add_theme(name="Cash timing", job_id=job_id)

    with pytest.raises(OutcomeNotFoundError):
        service.assign_theme([outcome_id, "no-such-outcome"], theme.id)

    stored = service.repo.get_outcome(outcome_id)
    assert stored is not None and stored.theme_ids == []


def test_assigning_the_same_theme_twice_does_not_duplicate_the_membership(
    service: ODIService,
) -> None:
    job_id = _job_id(service)
    outcome_id = _outcome(
        service, job_id, "Minimize the time it takes to find a payment when reconciling"
    )
    theme = service.add_theme(name="Cash timing", job_id=job_id)

    service.assign_theme([outcome_id], theme.id)
    again = service.assign_theme([outcome_id], theme.id)

    assert again[0].theme_ids == [theme.id]


def test_unassign_leaves_other_memberships_intact(service: ODIService) -> None:
    job_id = _job_id(service)
    outcome_id = _outcome(
        service, job_id, "Minimize the time it takes to find a payment when reconciling"
    )
    first = service.add_theme(name="Cash timing", job_id=job_id)
    second = service.add_theme(name="Approvals", job_id=job_id)
    service.assign_theme([outcome_id], first.id)
    service.assign_theme([outcome_id], second.id)

    updated = service.unassign_theme([outcome_id], first.id)

    assert updated[0].theme_ids == [second.id]


def test_unassigning_a_theme_that_was_never_assigned_changes_nothing(
    service: ODIService,
) -> None:
    job_id = _job_id(service)
    outcome_id = _outcome(
        service, job_id, "Minimize the time it takes to find a payment when reconciling"
    )
    theme = service.add_theme(name="Cash timing", job_id=job_id)

    updated = service.unassign_theme([outcome_id], theme.id)

    assert updated[0].theme_ids == []


def test_update_outcome_refuses_a_foreign_or_missing_theme_id(service: ODIService) -> None:
    from agentic_odi_core.services import ThemeNotFoundError

    job_id = _job_id(service)
    other = service.add_job("Onboard a supplier", None)
    outcome_id = _outcome(
        service, job_id, "Minimize the time it takes to find a payment when reconciling"
    )
    foreign = service.add_theme(name="Not yours", job_id=other.id)

    with pytest.raises(ValidationError):
        service.update_outcome(outcome_id, {"theme_ids": [foreign.id]})
    with pytest.raises(ThemeNotFoundError):
        service.update_outcome(outcome_id, {"theme_ids": ["no-such-theme"]})

    stored = service.repo.get_outcome(outcome_id)
    assert stored is not None and stored.theme_ids == []


# --- the service: deleting -----------------------------------------------------


def test_deleting_a_parent_reparents_children_and_keeps_every_other_membership(
    service: ODIService,
) -> None:
    job_id = _job_id(service)
    outcome_id = _outcome(
        service, job_id, "Minimize the time it takes to find a payment when reconciling"
    )
    parent = service.add_theme(name="Cash timing", job_id=job_id)
    child = service.add_theme(name="Payment windows", job_id=job_id, parent_id=parent.id)
    keeper = service.add_theme(name="Approvals", job_id=job_id)
    service.assign_theme([outcome_id], child.id)
    service.assign_theme([outcome_id], keeper.id)

    result = service.delete_theme(parent.id)

    assert result["reparented"] == [child.id]
    assert result["reparented_to"] is None
    assert service.get_theme(child.id).parent_id is None
    stored = service.repo.get_outcome(outcome_id)
    assert stored is not None and stored.theme_ids == [child.id, keeper.id]


def test_deleting_a_theme_drops_only_its_own_membership(service: ODIService) -> None:
    job_id = _job_id(service)
    outcome_id = _outcome(
        service, job_id, "Minimize the time it takes to find a payment when reconciling"
    )
    doomed = service.add_theme(name="Cash timing", job_id=job_id)
    keeper = service.add_theme(name="Approvals", job_id=job_id)
    service.assign_theme([outcome_id], doomed.id)
    service.assign_theme([outcome_id], keeper.id)

    service.delete_theme(doomed.id)

    surviving = service.repo.get_outcome(outcome_id)
    assert surviving is not None
    assert surviving.theme_ids == [keeper.id]


def test_deleting_a_theme_never_deletes_an_outcome(service: ODIService) -> None:
    job_id = _job_id(service)
    outcome_id = _outcome(
        service, job_id, "Minimize the time it takes to find a payment when reconciling"
    )
    theme = service.add_theme(name="Cash timing", job_id=job_id)
    service.assign_theme([outcome_id], theme.id)

    service.delete_theme(theme.id)

    assert service.repo.get_outcome(outcome_id) is not None


def test_deleting_a_missing_theme_fails(service: ODIService) -> None:
    from agentic_odi_core.services import ThemeNotFoundError

    with pytest.raises(ThemeNotFoundError):
        service.delete_theme("nope")

    assert service.list_themes() == []


# --- persistence and replay -----------------------------------------------------


def test_membership_and_tree_survive_a_sqlite_reload(tmp_path) -> None:
    from agentic_odi_core.sqlite_repository import SQLiteRepository

    db = str(tmp_path / "themes.db")
    svc = ODIService(SQLiteRepository(db_path=db))
    svc.add_job("Reconcile supplier invoices", None)
    job_id = svc.get_jobs()[0].id
    outcome_id = _outcome(
        svc, job_id, "Minimize the time it takes to find a payment when reconciling"
    )
    parent = svc.add_theme(name="Cash timing", job_id=job_id)
    child = svc.add_theme(name="Payment windows", job_id=job_id, parent_id=parent.id)
    doomed = svc.add_theme(name="Approvals", job_id=job_id)
    svc.assign_theme([outcome_id], child.id)
    svc.assign_theme([outcome_id], doomed.id)
    svc.delete_theme(parent.id)
    svc.delete_theme(doomed.id)

    reopened = ODIService(SQLiteRepository(db_path=db))

    assert [t.name for t in reopened.list_themes()] == ["Payment windows"]
    assert reopened.get_theme(child.id).parent_id is None
    restored_outcome = reopened.repo.get_outcome(outcome_id)
    assert restored_outcome is not None
    assert restored_outcome.theme_ids == [child.id]


def test_reopening_a_store_did_not_assign_invented_themes_to_legacy_rows(tmp_path) -> None:
    from agentic_odi_core.sqlite_repository import SQLiteRepository

    db = str(tmp_path / "legacy.db")
    first = ODIService(SQLiteRepository(db_path=db))
    first.add_job("Reconcile supplier invoices", None)
    job_id = first.get_jobs()[0].id
    outcome_id = _outcome(
        first, job_id, "Minimize the time it takes to find a payment when reconciling"
    )

    reopened = ODIService(SQLiteRepository(db_path=db))
    reopened.add_theme(name="Cash timing", job_id=job_id)

    stored = reopened.get_outcome(outcome_id)
    assert stored is not None and stored.theme_ids == []


def test_theme_state_is_the_same_through_both_repositories(tmp_path) -> None:
    from agentic_odi_core.repository import InMemoryRepository
    from agentic_odi_core.sqlite_repository import SQLiteRepository

    memory = ODIService(InMemoryRepository())
    disk = ODIService(SQLiteRepository(db_path=str(tmp_path / "parity.db")))
    for svc in (memory, disk):
        svc.add_job("Reconcile supplier invoices", None)
        job_id = svc.get_jobs()[0].id
        outcome_id = _outcome(
            svc, job_id, "Minimize the time it takes to find a payment when reconciling"
        )
        parent = svc.add_theme(name="Cash timing", job_id=job_id)
        child = svc.add_theme(name="Payment windows", job_id=job_id, parent_id=parent.id)
        svc.assign_theme([outcome_id], child.id)
        svc.delete_theme(parent.id)

    def shape(svc: ODIService) -> tuple:
        names = {t.id: t.name for t in svc.list_themes()}
        tree = sorted(
            (t.name, names.get(t.parent_id) if t.parent_id else None) for t in svc.list_themes()
        )
        filing = sorted(
            (o.statement, sorted(names.get(tid, tid) for tid in o.theme_ids))
            for o in svc.repo.outcomes.values()
        )
        return (tree, filing)

    assert shape(memory) == shape(disk)
    assert [t.parent_id for t in memory.list_themes()] == [t.parent_id for t in disk.list_themes()]
