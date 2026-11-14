"""One customer quote must not become three opportunities.

The evidence→outcome promotion path gives a quote an identity from fields it
already has (source plus normalized content), makes a repeat import link to the
outcome the first one created, and turns a deliberate second promotion into a
typed conflict rather than a duplicate the landscape would count as demand.
"""

from __future__ import annotations

import pytest
from agentic_odi_core.errors import AlreadyPromotedError
from agentic_odi_core.repository import (
    InMemoryRepository,
    compute_promotion_fingerprint,
    normalize_quote_text,
)
from agentic_odi_core.services import ODIService
from agentic_odi_core.sqlite_repository import SQLiteRepository

STATEMENT = "Minimize the time to review a quote when feedback arrives"


@pytest.fixture
def service() -> ODIService:
    return ODIService(InMemoryRepository())


def _quote(service: ODIService, job_id: str, content: str, *, name: str = "quote"):
    return service.add_evidence(
        source_name="grain",
        source_kind="mcp",
        name=name,
        content=content,
        job_id=job_id,
    )


def test_normalization_ignores_case_whitespace_quotes_and_punctuation() -> None:
    assert normalize_quote_text("  “Lost   2 hours on deploy.” ") == normalize_quote_text(
        "lost 2 hours on deploy"
    )


def test_fingerprint_excludes_relabelling_but_keeps_the_source() -> None:
    same = compute_promotion_fingerprint("mcp", "grain", "Lost 2 hours on deploy.")
    assert same == compute_promotion_fingerprint("mcp", "grain", "lost 2 hours on deploy")
    #: A different connector is a different source, so it is not the same quote.
    assert same != compute_promotion_fingerprint("mcp", "gong", "Lost 2 hours on deploy.")


def test_repeat_import_promotes_to_the_existing_outcome(service: ODIService) -> None:
    job = service.add_job("Secret rotation")
    first = _quote(service, job.id, "Lost 2 hours on deploy")
    outcome = service.promote_evidence(
        first.id, "outcome", job_id=job.id, statement=STATEMENT, importance=8.0, satisfaction=4.0
    )

    #: A second import of the same quote, relabelled, is a distinct row…
    second = _quote(service, job.id, "  lost 2 hours on deploy. ", name="Call recap")
    assert second.id != first.id

    #: …that promotes to the same outcome instead of a second opportunity.
    again = service.promote_evidence(
        second.id, "outcome", job_id=job.id, statement=STATEMENT, importance=8.0, satisfaction=4.0
    )
    assert again.id == outcome.id
    assert len(service.get_outcomes(job.id)) == 1
    #: The repeat import now links back to the one outcome.
    linked = service.get_evidence(second.id)
    assert linked is not None
    assert linked.outcome_id == outcome.id


def test_distinct_quotes_promote_separately(service: ODIService) -> None:
    job = service.add_job("Secret rotation")
    first = _quote(service, job.id, "Lost 2 hours on deploy")
    second = _quote(service, job.id, "Cannot find the runbook at 2am")
    service.promote_evidence(
        first.id, "outcome", job_id=job.id, statement=STATEMENT, importance=8.0, satisfaction=4.0
    )
    service.promote_evidence(
        second.id, "outcome", job_id=job.id, statement=STATEMENT, importance=7.0, satisfaction=3.0
    )
    assert len(service.get_outcomes(job.id)) == 2


def test_require_unpromoted_reports_the_existing_outcome(service: ODIService) -> None:
    job = service.add_job("Secret rotation")
    quote = _quote(service, job.id, "Lost 2 hours on deploy")
    outcome = service.promote_evidence(
        quote.id, "outcome", job_id=job.id, statement=STATEMENT, importance=8.0, satisfaction=4.0
    )
    with pytest.raises(AlreadyPromotedError) as raised:
        service.require_unpromoted(quote.id)
    assert raised.value.outcome_id == outcome.id


def test_force_promotes_again_when_it_is_deliberate(service: ODIService) -> None:
    job = service.add_job("Secret rotation")
    quote = _quote(service, job.id, "Lost 2 hours on deploy")
    first = service.promote_evidence(
        quote.id, "outcome", job_id=job.id, statement=STATEMENT, importance=8.0, satisfaction=4.0
    )
    forced = service.promote_evidence(
        quote.id,
        "outcome",
        job_id=job.id,
        statement=STATEMENT,
        importance=8.0,
        satisfaction=4.0,
        force=True,
    )
    assert forced.id != first.id
    assert len(service.get_outcomes(job.id)) == 2


def test_deleting_the_outcome_leaves_the_quote_promotable(tmp_path) -> None:
    service = ODIService(SQLiteRepository(db_path=str(tmp_path / "odi.db")))
    job = service.add_job("Secret rotation")
    quote = _quote(service, job.id, "Lost 2 hours on deploy")
    outcome = service.promote_evidence(
        quote.id, "outcome", job_id=job.id, statement=STATEMENT, importance=8.0, satisfaction=4.0
    )
    service.delete_outcome(outcome.id)

    #: The quote survives, unlinked, and can be promoted again.
    stored = service.get_evidence(quote.id)
    assert stored is not None
    assert stored.outcome_id is None
    assert service.promoted_outcome_for(quote.id) is None
    again = service.promote_evidence(
        quote.id, "outcome", job_id=job.id, statement=STATEMENT, importance=8.0, satisfaction=4.0
    )
    assert again.id != outcome.id
