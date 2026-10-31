"""Presenting the alternatives inventory to a reader (M2-07.2, ALH-166).

The pure renderers are the one place the brief, the CLI and the Studio wording
come from, so these tests pin the two facts that must never be conflated: an
inventory that was recorded and holds only ``nothing`` is not the same as an
inventory that was never recorded.
"""

from __future__ import annotations

import pytest
from agentic_odi_core import (
    NOT_YET_INVENTORIED,
    AlternativeObservation,
    InMemoryRepository,
    ODIService,
    format_alternative_line,
    render_alternative_lines,
    solution_label,
)


def _service() -> ODIService:
    return ODIService(InMemoryRepository())


def _job_and_outcome(service: ODIService) -> tuple[str, str]:
    job = service.add_job(name="Ship a service")
    outcome = service.add_outcome(
        job_id=job.id,
        statement="Minimize the time it takes to ship when a release is cut",
        importance=8.0,
        satisfaction=4.0,
    )
    return job.id, outcome.id


def test_an_empty_inventory_renders_not_yet_inventoried() -> None:
    """An un-inventoried outcome says so, and never claims no solution."""
    lines = render_alternative_lines([])

    assert lines == [f"_{NOT_YET_INVENTORIED}_"]
    assert "not yet inventoried" in lines[0]
    assert "no solution" not in lines[0]


def test_the_nothing_row_is_rendered_as_evidence_not_absence() -> None:
    """A recorded ``nothing`` row renders as a row, distinct from un-inventoried."""
    lines = render_alternative_lines(
        [AlternativeObservation(name="Nothing", kind="nothing", adequacy=1.0)]
    )

    assert len(lines) == 1
    assert "nothing" in lines[0]
    assert lines[0] != f"_{NOT_YET_INVENTORIED}_"


def test_multiple_alternatives_keep_input_order_and_pick_no_winner() -> None:
    """Several observations stay several; no primary is invented."""
    observations = [
        AlternativeObservation(name="Spreadsheet", kind="manual", adequacy=6.0, usage_n=12),
        AlternativeObservation(name="Agency", kind="service", adequacy=4.0),
    ]

    lines = render_alternative_lines(observations)

    assert len(lines) == 2
    assert "Spreadsheet" in lines[0]
    assert "Agency" in lines[1]


def test_an_unknown_usage_count_is_silent_not_zero() -> None:
    """A count that was not recorded does not render as a fabricated ``n=0``."""
    line = format_alternative_line(
        AlternativeObservation(name="Workaround", kind="workaround", adequacy=3.0)
    )

    assert "n=" not in line
    assert "adequacy 3" in line


def test_customer_text_is_escaped_for_markup() -> None:
    """A name or note carrying markup renders as characters, not HTML."""
    line = format_alternative_line(
        AlternativeObservation(
            name="<script>alert(1)</script>",
            kind="product",
            adequacy=5.0,
            note="a <b>bold</b> claim",
        )
    )

    assert "<script>" not in line
    assert "&lt;script&gt;" in line
    assert "&lt;b&gt;" in line


def test_unknown_solution_state_is_refused() -> None:
    """A new state cannot be silently read as a solution claim."""
    with pytest.raises(ValueError, match="unknown existing-solution state"):
        solution_label("maybe")


def test_solution_labels_distinguish_asked_and_not_asked() -> None:
    """The three states word differently; only ``yes`` records a solution."""
    yes = solution_label("yes")
    nothing = solution_label("no_linked_nothing")
    unknown = solution_label("no_link_at_all")

    assert len({yes, nothing, unknown}) == 3
    assert "not yet inventoried" in unknown


def test_job_read_returns_every_link_with_its_alternative() -> None:
    """The bulk read a facet needs: one call, every alternative for the job."""
    service = _service()
    job_id, outcome_id = _job_and_outcome(service)
    alternative = service.add_alternative(job_id=job_id, name="Spreadsheet", kind="manual")
    service.link_alternative(outcome_id=outcome_id, alternative_id=alternative.id, adequacy=6.0)

    triples = service.job_outcome_alternatives(job_id)

    assert [(outcome, alt.kind, link.adequacy) for outcome, alt, link in triples] == [
        (outcome_id, "manual", 6.0)
    ]


def test_job_read_does_not_leak_another_jobs_links() -> None:
    """A job read never returns another job's inventory."""
    service = _service()
    job_id, outcome_id = _job_and_outcome(service)
    other_job = service.add_job(name="Another job")
    other_outcome = service.add_outcome(
        job_id=other_job.id,
        statement="Minimize the time it takes to review when a change lands",
        importance=7.0,
        satisfaction=3.0,
    )
    mine = service.add_alternative(job_id=job_id, name="Mine", kind="product")
    theirs = service.add_alternative(job_id=other_job.id, name="Theirs", kind="product")
    service.link_alternative(outcome_id=outcome_id, alternative_id=mine.id, adequacy=7.0)
    service.link_alternative(outcome_id=other_outcome.id, alternative_id=theirs.id, adequacy=2.0)

    triples = service.job_outcome_alternatives(job_id)

    assert [alt.name for _, alt, _ in triples] == ["Mine"]


def test_a_cross_job_link_is_refused() -> None:
    """The core refuses a link that joins an outcome and an alternative in different jobs."""
    service = _service()
    _job_id, outcome_id = _job_and_outcome(service)
    other_job = service.add_job(name="Another job")
    theirs = service.add_alternative(job_id=other_job.id, name="Theirs", kind="product")

    with pytest.raises(Exception) as excinfo:
        service.link_alternative(outcome_id=outcome_id, alternative_id=theirs.id, adequacy=2.0)

    assert "same job" in str(excinfo.value)


def test_job_read_refuses_an_unknown_job() -> None:
    """An unknown job is refused, not reported as an empty inventory."""
    service = _service()

    with pytest.raises(Exception) as excinfo:
        service.job_outcome_alternatives("missing-job")

    assert "missing-job" in str(excinfo.value)


def test_unlinking_updates_the_bulk_read_without_orphans() -> None:
    """Unlinking through the core contract updates the facet read, no orphan."""
    service = _service()
    job_id, outcome_id = _job_and_outcome(service)
    alternative = service.add_alternative(job_id=job_id, name="Spreadsheet", kind="manual")
    service.link_alternative(outcome_id=outcome_id, alternative_id=alternative.id, adequacy=6.0)
    assert len(service.job_outcome_alternatives(job_id)) == 1

    service.unlink_alternative(outcome_id, alternative.id)

    assert service.job_outcome_alternatives(job_id) == []
    assert service.has_existing_solution(outcome_id) == "no_link_at_all"
