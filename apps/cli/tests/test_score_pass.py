"""Tests for the keyboard scoring pass (A9 · ALH-22).

Every write goes through the same ``update_outcome`` the API uses, so these
tests assert the store, not just the printed output.
"""

from __future__ import annotations

import json

from agentic_odi_cli.backend import LocalBackend
from agentic_odi_cli.cli import app
from typer.testing import CliRunner

STATEMENTS = [
    "Minimize the time it takes to onboard when a new hire starts",
    "Minimize the time it takes to get a laptop when someone joins",
    "Minimize the number of steps it takes to match invoices when the month closes",
    "Minimize the time it takes to approve access when a request arrives",
    "Minimize the likelihood of an error when entering data by hand",
]


def _job_with_outcomes(runner: CliRunner, db: str, count: int = 5) -> tuple[str, list[str]]:
    job = runner.invoke(app, ["--db", db, "jobs", "add", "--name", "Onboard", "--json"])
    job_id = json.loads(job.output)["id"]
    backend = LocalBackend(db_path=db)
    ids = []
    for statement in STATEMENTS[:count]:
        outcome = backend.call(
            "add_outcome",
            {
                "job_id": job_id,
                "statement": statement,
                "importance": 5.0,
                "satisfaction": 5.0,
            },
        )
        ids.append(outcome["id"])
    return job_id, ids


def _outcome(db: str, outcome_id: str) -> dict:
    return LocalBackend(db_path=db).call("get_outcome", {"outcome_id": outcome_id})


def test_scoring_three_of_five_leaves_two_untouched(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    _, ids = _job_with_outcomes(runner, db)

    result = runner.invoke(
        app,
        ["--db", db, "score", "--json"],
        input="9\n3\n8\n2\n7\n4\nq\n",
    )

    assert result.exit_code == 0, result.output
    summary = json.loads(result.output)
    assert summary["scored"] == 3
    assert _outcome(db, ids[0])["opportunity_score"] == 15.0
    assert _outcome(db, ids[1])["opportunity_score"] == 14.0
    assert _outcome(db, ids[2])["opportunity_score"] == 10.0
    # The two not reached keep their original pair.
    assert _outcome(db, ids[3])["importance"] == 5.0
    assert _outcome(db, ids[4])["satisfaction"] == 5.0


def test_an_out_of_range_entry_is_refused_for_that_prompt_only(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    _, ids = _job_with_outcomes(runner, db)

    # 11 is refused and re-prompted; 9 lands. Then quit.
    result = runner.invoke(
        app,
        ["--db", db, "score", "--json"],
        input="11\n9\n3\nq\n",
    )

    assert result.exit_code == 0, result.output
    summary = json.loads(result.output)
    assert summary["scored"] == 1
    assert _outcome(db, ids[0])["importance"] == 9.0


def test_undo_restores_both_previous_values(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    _, ids = _job_with_outcomes(runner, db)

    # score the first (9/3), then undo it, then quit.
    result = runner.invoke(
        app,
        ["--db", db, "score", "--json"],
        input="9\n3\nu\nq\n",
    )

    assert result.exit_code == 0, result.output
    summary = json.loads(result.output)
    assert summary["scored"] == 1
    assert summary["undone"] == 1
    restored = _outcome(db, ids[0])
    assert restored["importance"] == 5.0
    assert restored["satisfaction"] == 5.0


def test_undo_restores_a_truly_unscored_outcome_to_none(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    _, ids = _job_with_outcomes(runner, db, count=2)
    backend = LocalBackend(db_path=db)
    # Clear both pairs: truly unscored, no score and no hidden zero.
    for outcome_id in ids:
        backend.call(
            "update_outcome",
            {"outcome_id": outcome_id, "importance": None, "satisfaction": None},
        )

    # Score the first (8/4), then undo it at the second prompt, then quit.
    result = runner.invoke(
        app,
        ["--db", db, "score", "--json"],
        input="8\n4\nu\nq\n",
    )

    assert result.exit_code == 0, result.output
    summary = json.loads(result.output)
    assert summary["undone"] == 1
    restored = _outcome(db, ids[0])
    assert restored["importance"] is None
    assert restored["satisfaction"] is None


def test_skip_makes_no_write(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    _, ids = _job_with_outcomes(runner, db)

    result = runner.invoke(app, ["--db", db, "score", "--json"], input="s\nq\n")

    assert result.exit_code == 0, result.output
    summary = json.loads(result.output)
    assert summary["skipped"] == 5
    assert _outcome(db, ids[0])["importance"] == 5.0


def test_end_of_input_stops_without_further_writes(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    _, ids = _job_with_outcomes(runner, db)

    # Score one, then end-of-input with no further keys.
    result = runner.invoke(app, ["--db", db, "score", "--json"], input="9\n3\n")

    assert result.exit_code == 0, result.output
    assert _outcome(db, ids[0])["importance"] == 9.0
    assert _outcome(db, ids[1])["importance"] == 5.0


def test_unscored_filter_and_limit(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    job_id, ids = _job_with_outcomes(runner, db)
    backend = LocalBackend(db_path=db)
    # Clear three outcomes so --unscored has a working set of three.
    for outcome_id in ids[:3]:
        backend.call(
            "update_outcome",
            {"outcome_id": outcome_id, "importance": None, "satisfaction": None},
        )

    result = runner.invoke(
        app,
        ["--db", db, "score", "--unscored", "--limit", "1", "--json"],
        input="7\n4\n",
    )

    assert result.exit_code == 0, result.output
    summary = json.loads(result.output)
    assert summary["total"] == 1
    assert summary["scored"] == 1


def test_empty_selection_renders_an_honest_completion(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    runner.invoke(app, ["--db", db, "jobs", "add", "--name", "Empty", "--json"])

    result = runner.invoke(app, ["--db", db, "score", "--json"])

    assert result.exit_code == 0, result.output
    summary = json.loads(result.output)
    assert summary["total"] == 0
    assert summary["scored"] == 0
    assert "Nothing to score" in summary["message"]


def test_the_prompt_shows_the_customer_sentence_when_evidence_exists(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    _, ids = _job_with_outcomes(runner, db, count=1)
    backend = LocalBackend(db_path=db)
    backend.call(
        "add_evidence",
        {
            "source_name": "Ana onboarding",
            "source_kind": "interview",
            "name": "quote",
            "content": "Setup takes forever.",
            "outcome_id": ids[0],
        },
    )

    result = runner.invoke(app, ["--db", db, "score"], input="9\n3\n")

    assert result.exit_code == 0, result.output
    assert "Setup takes forever." in result.output


def test_the_prompt_says_when_no_customer_sentence_was_captured(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    _job_with_outcomes(runner, db, count=1)

    result = runner.invoke(app, ["--db", db, "score"], input="9\n3\n")

    assert result.exit_code == 0, result.output
    assert "no customer sentence captured" in result.output


def test_two_numbers_still_compute_a_score(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()

    result = runner.invoke(app, ["--db", db, "score", "8", "2"])

    assert result.exit_code == 0, result.output
    assert "Opportunity score: 14.00" in result.output


def test_one_number_is_refused(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()

    result = runner.invoke(app, ["--db", db, "score", "8"])

    assert result.exit_code == 2
