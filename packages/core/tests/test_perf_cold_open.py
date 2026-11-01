"""Cold-open budget for a 1,500-outcome study.

Two segments are measured here, each on its own line, because the fix differs
per segment:

1. **Store open** — ``SQLiteRepository._load_snapshot`` replaying the whole log.
2. **Canvas assembly** — the read pattern ``fetch_local_canvas`` uses: every
   job's map, every job's outcomes, all evidence, all scheduled work.

The SPA's first interactive render is the third segment and is measured in
``apps/studio`` (``src/components/canvas/opportunityLandscape.perf.test.tsx``),
because it is a browser cost, not a Python one.

The wall-clock bounds below are **deliberately loose** — roughly an order of
magnitude above the reference machine's number. A tight bound on a shared CI
runner fails on a busy box and gets deleted within a month; a loose one still
catches the regression this ticket exists to prevent (the pre-fix canvas
assembly was ~45x the fixed one). The robust check is
``test_perf_canvas_assembly_does_not_rescan_the_whole_log``: it counts rows read
rather than seconds, so it is deterministic on any machine.
"""

from __future__ import annotations

import time

import pytest
from agentic_odi_core.corpus import REFERENCE_JOBS, REFERENCE_OUTCOMES, build_corpus
from agentic_odi_core.intent_store import IntentStore
from agentic_odi_core.services import ODIService
from agentic_odi_core.sqlite_repository import SQLiteRepository

#: Loose per-segment ceiling, in seconds. Reference numbers and the reasoning
#: live in docs/development.md; this is the "fail on an order of magnitude"
#: bound, not the target.
SEGMENT_CEILING_SECONDS = 2.0
#: Cold-open runs; the median is reported so one slow run does not decide.
RUNS = 5


def _write_corpus(db_path: str) -> int:
    """Write the reference study and return the number of events it appended."""
    corpus = build_corpus(outcomes=REFERENCE_OUTCOMES, jobs=REFERENCE_JOBS)
    repo = SQLiteRepository(db_path)
    try:
        for job in corpus.jobs:
            repo.add_job(job)
        for step in corpus.steps:
            repo.add_step(step)
        for outcome in corpus.outcomes:
            repo.add_outcome(outcome)
        for record in corpus.evidence:
            repo.add_evidence(record)
        return len(repo.store.get_stream())
    finally:
        repo.close()


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    return ordered[len(ordered) // 2]


@pytest.fixture(scope="module")
def corpus_store(tmp_path_factory) -> tuple[str, int]:
    db_path = str(tmp_path_factory.mktemp("perf") / "corpus.db")
    return db_path, _write_corpus(db_path)


def _assemble_canvas(service: ODIService) -> dict:
    """The read pattern ``fetch_local_canvas`` performs, without the HTTP layer."""
    jobs = [job.model_dump() for job in service.get_jobs()]
    steps: list[dict] = []
    outcomes: list[dict] = []
    for job in jobs:
        steps.extend(step.model_dump() for step in service.get_job_map(job["id"]))
        outcomes.extend(outcome.model_dump() for outcome in service.get_outcomes(job["id"]))
    evidence = [item.model_dump() for item in service.list_evidence()]
    scheduled = [item.model_dump() for item in service.list_scheduled_work()]
    return {
        "jobs": jobs,
        "steps": steps,
        "outcomes": outcomes,
        "evidence": evidence,
        "scheduled_work": scheduled,
    }


def test_perf_corpus_generator_is_deterministic() -> None:
    """Running the builder twice must produce identical records and digest."""
    first = build_corpus(outcomes=REFERENCE_OUTCOMES, jobs=REFERENCE_JOBS)
    second = build_corpus(outcomes=REFERENCE_OUTCOMES, jobs=REFERENCE_JOBS)

    assert first.counts() == {
        "jobs": REFERENCE_JOBS,
        "steps": REFERENCE_JOBS * 8,
        "outcomes": REFERENCE_OUTCOMES,
        "evidence": REFERENCE_OUTCOMES,
    }
    assert first.digest() == second.digest()
    assert first == second


def test_perf_store_open_is_under_the_loose_ceiling(corpus_store) -> None:
    db_path, _ = corpus_store
    samples: list[float] = []
    for _ in range(RUNS):
        start = time.perf_counter()
        repo = SQLiteRepository(db_path)
        samples.append(time.perf_counter() - start)
        repo.close()

    median = _median(samples)
    assert median < SEGMENT_CEILING_SECONDS, f"store open median {median:.3f}s"


def test_perf_canvas_assembly_is_under_the_loose_ceiling(corpus_store) -> None:
    db_path, _ = corpus_store
    repo = SQLiteRepository(db_path)
    service = ODIService(repo)
    try:
        samples: list[float] = []
        for _ in range(RUNS):
            start = time.perf_counter()
            canvas = _assemble_canvas(service)
            samples.append(time.perf_counter() - start)

        assert len(canvas["outcomes"]) == REFERENCE_OUTCOMES
        median = _median(samples)
        assert median < SEGMENT_CEILING_SECONDS, f"canvas assembly median {median:.3f}s"
    finally:
        repo.close()


def test_perf_canvas_assembly_does_not_rescan_the_whole_log(
    corpus_store, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The deterministic regression guard.

    Before the fix, every repository read re-parsed the entire event log, so one
    canvas assembly read ``reads x events`` rows. The fix reads each event once
    per assembly. The bound is a small multiple of the log length, not a
    wall-clock number, so a busy runner cannot make it flaky — but a return to
    the full rescan (an order of magnitude more rows) fails it.
    """
    db_path, event_count = corpus_store
    rows_read = 0
    original = IntentStore.get_stream

    def counting_get_stream(self, **kwargs):  # type: ignore[no-untyped-def]
        nonlocal rows_read
        events = original(self, **kwargs)
        rows_read += len(events)
        return events

    monkeypatch.setattr(IntentStore, "get_stream", counting_get_stream)

    repo = SQLiteRepository(db_path)
    service = ODIService(repo)
    try:
        rows_read = 0
        _assemble_canvas(service)
    finally:
        repo.close()

    # Each event is read at most once per store open plus once for the canvas,
    # with slack for the fixture's own setup reads. A full rescan is ~45x this.
    assert rows_read <= event_count * 4, f"read {rows_read} rows for {event_count} events"
