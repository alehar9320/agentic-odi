"""A1 — Interview records and quotes, persisted (ALH-14)."""

from __future__ import annotations

import pytest
from agentic_odi_core import ODIService
from agentic_odi_core.models import Interview, InterviewQuote
from agentic_odi_core.repository import InMemoryRepository
from agentic_odi_core.services import InterviewNotFoundError
from agentic_odi_core.sqlite_repository import SQLiteRepository


def _service(repo=None) -> ODIService:
    return ODIService(repo or InMemoryRepository())


def test_one_interview_with_three_quotes_round_trips_a_reload(tmp_path) -> None:
    db = str(tmp_path / "odi.db")
    service = _service(SQLiteRepository(db))
    interview = service.add_interview(
        title="Ana — onboarding",
        participant_label="Ana",
        participant_role="Ops lead",
    )
    for text in ("first", "second", "third"):
        service.add_quote(interview.id, text)

    service.repo.reload()  # type: ignore[attr-defined]

    assert service.get_interview(interview.id) == interview
    quotes = service.list_quotes(interview.id)
    assert [q.text for q in quotes] == ["first", "second", "third"]


def test_quotes_come_back_in_ordinal_order() -> None:
    service = _service()
    interview = service.add_interview(title="T", participant_label="P")
    service.add_quote(interview.id, "a")
    service.add_quote(interview.id, "b")
    service.add_quote(interview.id, "c")

    assert [q.ordinal for q in service.list_quotes(interview.id)] == [0, 1, 2]


def test_deleting_the_interview_removes_its_quotes_and_nothing_else() -> None:
    service = _service()
    keep = service.add_interview(title="Keep", participant_label="P")
    drop = service.add_interview(title="Drop", participant_label="Q")
    dropped_quote = service.add_quote(drop.id, "gone")
    service.add_quote(keep.id, "stays")

    removed = service.delete_interview(drop.id)

    assert removed == [dropped_quote.id]
    assert service.list_quotes(drop.id) == []
    assert [q.text for q in service.list_quotes(keep.id)] == ["stays"]


def test_get_odi_schema_exposes_both_models() -> None:
    from agentic_odi_core import odi_schema

    schema = odi_schema()
    assert "Interview" in schema
    assert "InterviewQuote" in schema


def test_missing_interview_rejects_quote_creation_without_events() -> None:
    repo = InMemoryRepository()
    service = _service(repo)
    before = len(repo.quotes)

    with pytest.raises(InterviewNotFoundError):
        service.add_quote("does-not-exist", "hello")

    assert len(repo.quotes) == before


def test_equal_creation_timestamps_still_produce_deterministic_ordinals() -> None:
    service = _service()
    interview = service.add_interview(title="T", participant_label="P")
    ids = [service.add_quote(interview.id, f"q{i}").id for i in range(3)]

    quotes = service.list_quotes(interview.id)
    assert [q.id for q in quotes] == ids
    assert [q.ordinal for q in quotes] == [0, 1, 2]


def test_delete_interview_records_cascade_in_the_event_payload(tmp_path) -> None:
    db = str(tmp_path / "odi.db")
    service = _service(SQLiteRepository(db))
    interview = service.add_interview(title="T", participant_label="P")
    q1 = service.add_quote(interview.id, "one")
    q2 = service.add_quote(interview.id, "two")

    service.delete_interview(interview.id)

    events = service.repo.store.get_stream()  # type: ignore[attr-defined]
    deleted = [e for e in events if e["type"] == "INTERVIEW_DELETED"]
    assert len(deleted) == 1
    assert sorted(deleted[0]["payload"]["cascaded_quote_ids"]) == sorted([q1.id, q2.id])


def test_delete_missing_interview_raises() -> None:
    service = _service()
    with pytest.raises(InterviewNotFoundError):
        service.delete_interview("nope")


def test_interview_update_round_trips(tmp_path) -> None:
    db = str(tmp_path / "odi.db")
    service = _service(SQLiteRepository(db))
    interview = service.add_interview(title="T", participant_label="P")

    updated = service.update_interview(interview.id, {"title": "Renamed"})

    assert updated.title == "Renamed"
    service.repo.reload()  # type: ignore[attr-defined]
    assert service.get_interview(interview.id).title == "Renamed"  # type: ignore[union-attr]


def test_interview_rejects_missing_job() -> None:
    from agentic_odi_core import JobNotFoundError

    service = _service()
    with pytest.raises(JobNotFoundError):
        service.add_interview(title="T", participant_label="P", job_id="missing")


def test_list_interviews_filters_by_job() -> None:
    service = _service()
    job = service.add_job("Onboard")
    a = service.add_interview(title="A", participant_label="P", job_id=job.id)
    service.add_interview(title="B", participant_label="Q")

    assert [i.id for i in service.list_interviews(job_id=job.id)] == [a.id]
    assert len(service.list_interviews()) == 2


def test_quote_model_requires_ordinal() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        InterviewQuote(interview_id="i", text="x")  # type: ignore[call-arg]


def test_interview_model_defaults_source_kind_to_manual() -> None:
    assert Interview(title="T", participant_label="P").source_kind == "manual"


def test_import_transcript_is_atomic_on_parse_failure() -> None:
    from agentic_odi_core import InMemoryRepository, ODIService
    from agentic_odi_core.transcript import TranscriptFormatError

    service = ODIService(InMemoryRepository())
    with pytest.raises(TranscriptFormatError):
        service.import_transcript(
            "WEBVTT\n\n00:00:1.0 --> nope\nhello\n",
            title="T",
            participant_label="P",
        )
    # Nothing was written: the parse happens before the first write.
    assert service.list_interviews() == []


def test_import_transcript_persists_turns_as_ordered_quotes() -> None:
    from agentic_odi_core import InMemoryRepository, ODIService

    service = ODIService(InMemoryRepository())
    interview, quotes = service.import_transcript(
        "**Ana:** one\n\n**Bo:** two\n",
        title="T",
        participant_label="Ana",
    )
    assert [q.text for q in quotes] == ["one", "two"]
    assert [q.ordinal for q in quotes] == [0, 1]
    assert [q.interview_id for q in quotes] == [interview.id, interview.id]
    assert service.list_quotes(interview.id) == quotes
