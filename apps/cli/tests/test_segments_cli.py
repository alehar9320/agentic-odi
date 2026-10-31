"""Tests for `odi segments` (D1–D4, ALH-40…ALH-43).

Pinned choices:

* ``segments add|list|show|delete`` are transport only; the service owns
  membership validation and the CLI never recomputes a count.
* ``segments suggest`` writes nothing; ``segments accept`` takes the fingerprint
  it printed.
* ``segments profile`` prints ``not measured`` for a ratio of nothing, never
  ``0``.
* ``segments strategy`` refuses a kind the data does not support and exits
  nonzero, no traceback.
"""

from __future__ import annotations

import json

from agentic_odi_cli.cli import app
from typer.testing import CliRunner

runner = CliRunner()

_STATEMENTS = (
    "Minimize the time it takes to publish a plugin when a release is ready",
    "Minimize the cost of supporting a plugin when it ships",
    "Minimize the time it takes to resolve a support ticket after a bug",
)


def _statement(index: int) -> str:
    if index < len(_STATEMENTS):
        return _STATEMENTS[index]
    return f"Minimize the time it takes to publish plugin {index} when a release is ready"


def _seed(db: str, scores: list[tuple[float, float]]) -> tuple[str, list[str]]:
    job = runner.invoke(app, ["--db", db, "jobs", "add", "--name", "Publish a plugin", "--json"])
    assert job.exit_code == 0, job.output
    job_id = json.loads(job.output)["id"]
    ids = []
    for index, (importance, satisfaction) in enumerate(scores):
        outcome = runner.invoke(
            app,
            [
                "--db",
                db,
                "desired-outcomes",
                "add",
                "--job-id",
                job_id,
                "--statement",
                _statement(index),
                "--importance",
                str(importance),
                "--satisfaction",
                str(satisfaction),
                "--json",
            ],
        )
        assert outcome.exit_code == 0, outcome.output
        ids.append(json.loads(outcome.output)["id"])
    return job_id, ids


def test_add_list_show_delete_roundtrip(tmp_path) -> None:
    db = str(tmp_path / "segments.db")
    job_id, ids = _seed(db, [(9, 3), (8, 4), (7, 3)])

    added = runner.invoke(
        app,
        [
            "--db",
            db,
            "segments",
            "add",
            "--job-id",
            job_id,
            "--name",
            "Release engineers",
            "--criterion",
            "They own the publish step.",
            "--outcome-id",
            ids[0],
            "--outcome-id",
            ids[1],
            "--json",
        ],
    )
    assert added.exit_code == 0, added.output
    segment_id = json.loads(added.output)["id"]

    listed = runner.invoke(app, ["--db", db, "segments", "list", "--job-id", job_id, "--json"])
    assert listed.exit_code == 0, listed.output
    assert [s["id"] for s in json.loads(listed.output)] == [segment_id]

    shown = runner.invoke(app, ["--db", db, "segments", "show", "--segment-id", segment_id])
    assert shown.exit_code == 0, shown.output
    assert "Release engineers" in shown.output

    deleted = runner.invoke(app, ["--db", db, "segments", "delete", "--segment-id", segment_id])
    assert deleted.exit_code == 0, deleted.output
    remaining = runner.invoke(app, ["--db", db, "segments", "list", "--job-id", job_id, "--json"])
    assert json.loads(remaining.output) == []


def test_suggest_then_accept(tmp_path) -> None:
    db = str(tmp_path / "accept.db")
    job_id, _ = _seed(db, [(9, 3), (9, 2), (9, 4), (3, 9), (3, 9), (3, 9)])

    suggested = runner.invoke(
        app, ["--db", db, "segments", "suggest", "--job-id", job_id, "--json"]
    )
    assert suggested.exit_code == 0, suggested.output
    candidates = json.loads(suggested.output)["candidates"]
    assert candidates
    fingerprint = candidates[0]["fingerprint"]

    # Suggesting wrote nothing.
    before = runner.invoke(app, ["--db", db, "segments", "list", "--job-id", job_id, "--json"])
    assert json.loads(before.output) == []

    accepted = runner.invoke(
        app,
        [
            "--db",
            db,
            "segments",
            "accept",
            "--job-id",
            job_id,
            "--fingerprint",
            fingerprint,
            "--json",
        ],
    )
    assert accepted.exit_code == 0, accepted.output
    segment = json.loads(accepted.output)
    assert segment["origin"] == "candidate"


def test_profile_prints_not_measured_for_a_ratio_of_nothing(tmp_path) -> None:
    db = str(tmp_path / "profile.db")
    job_id, ids = _seed(db, [(9, 3), (8, 4), (7, 3)])
    added = runner.invoke(
        app,
        [
            "--db",
            db,
            "segments",
            "add",
            "--job-id",
            job_id,
            "--name",
            "One",
            "--criterion",
            "single member",
            "--outcome-id",
            ids[0],
            "--json",
        ],
    )
    segment_id = json.loads(added.output)["id"]
    # Delete the only member so nothing is measured and the membership dangles.
    deleted = runner.invoke(app, ["--db", db, "desired-outcomes", "delete", ids[0], "--yes"])
    assert deleted.exit_code == 0, deleted.output

    profiled = runner.invoke(app, ["--db", db, "segments", "profile", "--segment-id", segment_id])
    assert profiled.exit_code == 0, profiled.output
    assert "not measured" in profiled.output


def test_strategy_refusal_exits_nonzero(tmp_path) -> None:
    db = str(tmp_path / "strategy.db")
    job_id, ids = _seed(db, [(3, 9), (3, 9), (3, 9)])
    added = runner.invoke(
        app,
        [
            "--db",
            db,
            "segments",
            "add",
            "--job-id",
            job_id,
            "--name",
            "Overserved",
            "--criterion",
            "all overserved",
            "--outcome-id",
            ids[0],
            "--json",
        ],
    )
    segment_id = json.loads(added.output)["id"]
    refused = runner.invoke(
        app,
        [
            "--db",
            db,
            "segments",
            "strategy",
            "--segment-id",
            segment_id,
            "--kind",
            "differentiated",
            "--rationale",
            "no",
            "--expected-effect",
            "no",
        ],
    )
    assert refused.exit_code != 0
    assert "underserved" in refused.output


def test_strategy_records_and_lists(tmp_path) -> None:
    db = str(tmp_path / "ok.db")
    job_id, ids = _seed(db, [(9, 3), (9, 2), (9, 4)])
    added = runner.invoke(
        app,
        [
            "--db",
            db,
            "segments",
            "add",
            "--job-id",
            job_id,
            "--name",
            "Underserved",
            "--criterion",
            "all underserved",
            "--outcome-id",
            ids[0],
            "--json",
        ],
    )
    segment_id = json.loads(added.output)["id"]
    recorded = runner.invoke(
        app,
        [
            "--db",
            db,
            "segments",
            "strategy",
            "--segment-id",
            segment_id,
            "--kind",
            "differentiated",
            "--rationale",
            "The gap is real.",
            "--expected-effect",
            "Better publish times.",
            "--json",
        ],
    )
    assert recorded.exit_code == 0, recorded.output
    listed = runner.invoke(
        app, ["--db", db, "segments", "strategies", "--segment-id", segment_id, "--json"]
    )
    assert listed.exit_code == 0, listed.output
    assert len(json.loads(listed.output)) == 1


def test_human_readable_outputs_cover_every_subcommand(tmp_path) -> None:
    """The default (non-JSON) renderings are transport, and must stay readable."""
    db = str(tmp_path / "human.db")
    job_id, ids = _seed(db, [(9, 3), (9, 2), (9, 4), (3, 9), (3, 9), (3, 9)])

    # Empty states first: no segments, no strategies, no candidates yet.
    empty_list = runner.invoke(app, ["--db", db, "segments", "list", "--job-id", job_id])
    assert empty_list.exit_code == 0, empty_list.output
    assert "No segments recorded yet." in empty_list.output
    empty_strategies = runner.invoke(app, ["--db", db, "segments", "strategies"])
    assert empty_strategies.exit_code == 0, empty_strategies.output
    assert "No strategies recorded yet." in empty_strategies.output

    added = runner.invoke(
        app,
        [
            "--db",
            db,
            "segments",
            "add",
            "--job-id",
            job_id,
            "--name",
            "Release engineers",
            "--criterion",
            "They own the publish step.",
            "--outcome-id",
            ids[0],
            "--outcome-id",
            ids[1],
        ],
    )
    assert added.exit_code == 0, added.output
    assert "Segment created:" in added.output

    listed = runner.invoke(app, ["--db", db, "segments", "list", "--job-id", job_id])
    assert listed.exit_code == 0, listed.output
    assert "Release engineers" in listed.output

    shown = runner.invoke(
        app,
        [
            "--db",
            db,
            "segments",
            "show",
            "--segment-id",
            json.loads(
                runner.invoke(
                    app,
                    ["--db", db, "segments", "list", "--job-id", job_id, "--json"],
                ).output,
            )[0]["id"],
        ],
    )
    assert shown.exit_code == 0, shown.output
    assert "Criterion: They own the publish step." in shown.output

    profiled = runner.invoke(
        app,
        [
            "--db",
            db,
            "segments",
            "profile",
            "--segment-id",
            json.loads(
                runner.invoke(
                    app,
                    ["--db", db, "segments", "list", "--job-id", job_id, "--json"],
                ).output,
            )[0]["id"],
        ],
    )
    assert profiled.exit_code == 0, profiled.output
    assert "Top underserved:" in profiled.output

    suggested = runner.invoke(app, ["--db", db, "segments", "suggest", "--job-id", job_id])
    assert suggested.exit_code == 0, suggested.output
    assert "Underserved outcomes" in suggested.output

    segment_id = json.loads(
        runner.invoke(app, ["--db", db, "segments", "list", "--job-id", job_id, "--json"]).output
    )[0]["id"]
    recorded = runner.invoke(
        app,
        [
            "--db",
            db,
            "segments",
            "strategy",
            "--segment-id",
            segment_id,
            "--kind",
            "differentiated",
            "--rationale",
            "The gap is real.",
            "--expected-effect",
            "Better publish times.",
        ],
    )
    assert recorded.exit_code == 0, recorded.output
    assert "Strategy recorded:" in recorded.output

    strategies = runner.invoke(app, ["--db", db, "segments", "strategies"])
    assert strategies.exit_code == 0, strategies.output
    assert "The gap is real." in strategies.output

    deleted = runner.invoke(app, ["--db", db, "segments", "delete", "--segment-id", segment_id])
    assert deleted.exit_code == 0, deleted.output
    assert "Segment deleted:" in deleted.output


def test_suggest_with_no_group_reports_a_reason(tmp_path) -> None:
    """A job whose scores form no group says why, rather than an empty table."""
    db = str(tmp_path / "none.db")
    job_id, _ = _seed(db, [(9, 3), (3, 9)])

    suggested = runner.invoke(app, ["--db", db, "segments", "suggest", "--job-id", job_id])

    assert suggested.exit_code == 0, suggested.output
    assert "candidates" not in suggested.output
    assert "scored" in suggested.output.lower()
