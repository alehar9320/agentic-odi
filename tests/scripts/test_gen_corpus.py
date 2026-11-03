"""The committed corpus generator produces the documented study, deterministically."""

from __future__ import annotations

import sqlite3

import gen_corpus
from agentic_odi_core.corpus import REFERENCE_JOBS, REFERENCE_OUTCOMES, build_corpus
from agentic_odi_core.sqlite_repository import SQLiteRepository


def _count_events(db_path: str, event_type: str) -> int:
    with sqlite3.connect(db_path) as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM events WHERE event_type = ?", (event_type,)
        ).fetchone()[0]


def test_generator_writes_the_documented_counts(tmp_path) -> None:
    db_path = str(tmp_path / "corpus.db")

    assert gen_corpus.main(["--out", db_path]) == 0

    assert _count_events(db_path, "JOB_CREATED") == REFERENCE_JOBS
    assert _count_events(db_path, "STEP_CREATED") == REFERENCE_JOBS * 8
    assert _count_events(db_path, "OUTCOME_CREATED") == REFERENCE_OUTCOMES
    assert _count_events(db_path, "EVIDENCE_CREATED") == REFERENCE_OUTCOMES


def test_running_the_generator_twice_produces_the_same_records(tmp_path) -> None:
    first = str(tmp_path / "first.db")
    second = str(tmp_path / "second.db")

    gen_corpus.main(["--out", first])
    gen_corpus.main(["--out", second])

    # The event id and timestamp are store metadata and differ per run; the
    # records the generator chooses are what must be identical.
    def dump(db_path: str) -> list[tuple]:
        with sqlite3.connect(db_path) as conn:
            return conn.execute("SELECT event_type, payload FROM events ORDER BY id").fetchall()

    assert dump(first) == dump(second)


def test_generator_replays_into_the_reference_study(tmp_path) -> None:
    db_path = str(tmp_path / "corpus.db")
    gen_corpus.main(["--out", db_path])

    repo = SQLiteRepository(db_path)
    try:
        assert len(repo.list_jobs()) == REFERENCE_JOBS
        assert len(repo.list_evidence()) == REFERENCE_OUTCOMES
        outcomes = [outcome for job in repo.list_jobs() for outcome in repo.get_outcomes(job.id)]
        assert len(outcomes) == REFERENCE_OUTCOMES
    finally:
        repo.close()

    assert build_corpus().digest() == build_corpus().digest()
