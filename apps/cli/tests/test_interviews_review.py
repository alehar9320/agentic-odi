"""Tests for the keyboard review pass (A5.2 · ALH-153).

Every decision drives the same service the API uses, so these tests assert the
store, not just the printed output.
"""

from __future__ import annotations

import json

from agentic_odi_cli.backend import LocalBackend
from agentic_odi_cli.cli import app
from typer.testing import CliRunner

THREE_NEEDS = (
    "Setup takes forever when a new hire starts. "
    "We wait days for a laptop when someone joins. "
    "Matching invoices by hand costs hours when the month closes."
)


def _interview_with_candidates(runner: CliRunner, db: str, text: str = THREE_NEEDS) -> str:
    """An interview linked to a job, with candidates extracted from one quote."""
    job = runner.invoke(app, ["--db", db, "jobs", "add", "--name", "Onboard", "--json"])
    job_id = json.loads(job.output)["id"]
    interview = runner.invoke(
        app,
        [
            "--db",
            db,
            "interviews",
            "add",
            "--title",
            "Ana — onboarding",
            "--participant",
            "Ana",
            "--job-id",
            job_id,
            "--json",
        ],
    )
    interview_id = json.loads(interview.output)["id"]
    backend = LocalBackend(db_path=db)
    quote_id = backend.call("add_quote", {"interview_id": interview_id, "text": text})["id"]
    runner.invoke(app, ["--db", db, "interviews", "extract", quote_id, "--json"])
    return interview_id


def _candidates(db: str, status: str | None = None) -> list[dict]:
    backend = LocalBackend(db_path=db)
    args: dict = {"offset": 0}
    if status is not None:
        args["status"] = status
    return backend.call("list_candidates", args)


def test_three_decisions_through_scripted_stdin(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    interview_id = _interview_with_candidates(runner, db)
    candidates = _candidates(db, "proposed")
    assert len(candidates) == 3

    # accept the first, reject the second, skip the third
    result = runner.invoke(
        app,
        [
            "--db",
            db,
            "interviews",
            "review",
            interview_id,
            "--importance",
            "8",
            "--satisfaction",
            "3",
            "--json",
        ],
        input="a\nr\nnot a real need\ns\n",
    )

    assert result.exit_code == 0, result.output
    summary = json.loads(result.output)
    assert summary["accepted"] == 1
    assert summary["rejected"] == 1
    assert summary["skipped"] == 1

    by_id = {c["id"]: c for c in _candidates(db)}
    assert by_id[candidates[0]["id"]]["status"] == "accepted"
    assert by_id[candidates[0]["id"]]["outcome_id"]
    assert by_id[candidates[1]["id"]]["status"] == "rejected"
    assert by_id[candidates[1]["id"]]["decision_reason"] == "not a real need"
    assert by_id[candidates[2]["id"]]["status"] == "proposed"


def test_skip_changes_nothing(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    interview_id = _interview_with_candidates(runner, db)

    result = runner.invoke(
        app, ["--db", db, "interviews", "review", interview_id, "--json"], input="s\ns\ns\n"
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["skipped"] == 3
    assert len(_candidates(db, "proposed")) == 3


def test_accept_prompts_for_scores_when_not_supplied(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    interview_id = _interview_with_candidates(
        runner, db, "Setup takes forever when a new hire starts."
    )

    result = runner.invoke(
        app, ["--db", db, "interviews", "review", interview_id, "--json"], input="a\n8\n3\n"
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["accepted"] == 1
    accepted = _candidates(db, "accepted")
    assert len(accepted) == 1


def test_edit_with_a_validation_error_then_a_valid_statement(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    interview_id = _interview_with_candidates(
        runner, db, "Setup takes forever when a new hire starts."
    )

    # edit to a blank statement first (refused), then to a valid one
    result = runner.invoke(
        app,
        [
            "--db",
            db,
            "interviews",
            "review",
            interview_id,
            "--importance",
            "8",
            "--satisfaction",
            "3",
            "--json",
        ],
        input="e\n\ne\nMinimize the time it takes to onboard a new hire when a hire joins\n",
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["accepted"] == 1
    accepted = _candidates(db, "accepted")
    assert accepted[0]["statement"] == (
        "Minimize the time it takes to onboard a new hire when a hire joins"
    )


def test_reject_needs_a_reason_and_keeps_the_candidate(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    interview_id = _interview_with_candidates(
        runner, db, "Setup takes forever when a new hire starts."
    )

    # a blank reason is refused; the loop re-prompts and the second reason lands
    result = runner.invoke(
        app,
        ["--db", db, "interviews", "review", interview_id, "--json"],
        input="r\n\nr\ncovered by another outcome\n",
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["rejected"] == 1
    rejected = _candidates(db, "rejected")
    assert rejected[0]["decision_reason"] == "covered by another outcome"


def test_merge_needs_an_explicit_target(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    interview_id = _interview_with_candidates(
        runner,
        db,
        "Setup takes forever when a new hire starts. We wait days for a laptop when someone joins.",
    )

    # accept the first candidate to produce a target outcome
    accept = runner.invoke(
        app,
        [
            "--db",
            db,
            "candidates",
            "accept",
            _candidates(db, "proposed")[0]["id"],
            "--importance",
            "8",
            "--satisfaction",
            "3",
            "--json",
        ],
    )
    target = json.loads(accept.output)["outcome"]["id"]

    # a blank target is refused, then the real target merges the second candidate
    result = runner.invoke(
        app,
        ["--db", db, "interviews", "review", interview_id, "--json"],
        input=f"m\n\nm\n{target}\n",
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["merged"] == 1
    merged = _candidates(db, "merged")
    assert merged[0]["merged_into"] == target


def test_quit_preserves_every_remaining_candidate(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    interview_id = _interview_with_candidates(runner, db)

    result = runner.invoke(
        app,
        [
            "--db",
            db,
            "interviews",
            "review",
            interview_id,
            "--importance",
            "8",
            "--satisfaction",
            "3",
            "--json",
        ],
        input="a\nq\n",
    )

    assert result.exit_code == 0, result.output
    summary = json.loads(result.output)
    assert summary["accepted"] == 1
    assert summary["skipped"] == 2
    assert len(_candidates(db, "proposed")) == 2


def test_end_of_input_preserves_every_remaining_candidate(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    interview_id = _interview_with_candidates(runner, db)

    # accept one, then run out of input
    result = runner.invoke(
        app,
        [
            "--db",
            db,
            "interviews",
            "review",
            interview_id,
            "--importance",
            "8",
            "--satisfaction",
            "3",
            "--json",
        ],
        input="a\n",
    )

    assert result.exit_code == 0, result.output
    summary = json.loads(result.output)
    assert summary["accepted"] == 1
    assert summary["skipped"] == 2
    assert len(_candidates(db, "proposed")) == 2


def test_yes_accepts_every_proposed_candidate(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    interview_id = _interview_with_candidates(runner, db)

    result = runner.invoke(
        app,
        [
            "--db",
            db,
            "interviews",
            "review",
            interview_id,
            "--yes",
            "--importance",
            "8",
            "--satisfaction",
            "3",
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    summary = json.loads(result.output)
    assert summary["accepted"] == 3
    assert summary["failed"] == 0
    assert _candidates(db, "proposed") == []
    assert len(_candidates(db, "accepted")) == 3


def test_yes_touches_only_proposed_candidates(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    interview_id = _interview_with_candidates(runner, db)

    rejected_id = _candidates(db, "proposed")[0]["id"]
    runner.invoke(
        app, ["--db", db, "candidates", "reject", rejected_id, "--reason", "no", "--json"]
    )

    result = runner.invoke(
        app,
        [
            "--db",
            db,
            "interviews",
            "review",
            interview_id,
            "--yes",
            "--importance",
            "8",
            "--satisfaction",
            "3",
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    summary = json.loads(result.output)
    assert summary["accepted"] == 2
    # the already-rejected row is untouched
    rejected = {c["id"]: c for c in _candidates(db)}[rejected_id]
    assert rejected["status"] == "rejected"


def test_yes_requires_scores(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    interview_id = _interview_with_candidates(runner, db)

    result = runner.invoke(
        app, ["--db", db, "interviews", "review", interview_id, "--yes", "--json"]
    )

    assert result.exit_code == 2
    assert "importance" in result.output.lower()
    # nothing was written
    assert len(_candidates(db, "proposed")) == 3


def test_empty_queue_prints_a_zero_work_result(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    job = runner.invoke(app, ["--db", db, "jobs", "add", "--name", "Onboard", "--json"])
    job_id = json.loads(job.output)["id"]
    interview = runner.invoke(
        app,
        [
            "--db",
            db,
            "interviews",
            "add",
            "--title",
            "T",
            "--participant",
            "Ana",
            "--job-id",
            job_id,
            "--json",
        ],
    )
    interview_id = json.loads(interview.output)["id"]

    result = runner.invoke(app, ["--db", db, "interviews", "review", interview_id, "--json"])

    assert result.exit_code == 0, result.output
    summary = json.loads(result.output)
    assert summary["accepted"] == 0
    assert "nothing to review" in summary["message"].lower()


def test_rerunning_does_not_duplicate_outcomes_or_evidence(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    interview_id = _interview_with_candidates(runner, db)

    args = [
        "--db",
        db,
        "interviews",
        "review",
        interview_id,
        "--yes",
        "--importance",
        "8",
        "--satisfaction",
        "3",
        "--json",
    ]
    runner.invoke(app, args)
    # the second pass has nothing proposed, so it accepts nothing new
    second = runner.invoke(app, args)

    assert second.exit_code == 0, second.output
    assert json.loads(second.output)["accepted"] == 0
    assert len(_candidates(db, "accepted")) == 3
