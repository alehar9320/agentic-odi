"""Tests for the candidates CLI group and the interviews extract command (A4)."""

from __future__ import annotations

import json

from agentic_odi_cli.backend import LocalBackend
from agentic_odi_cli.cli import app
from typer.testing import CliRunner

QUOTE = "Setup takes forever when a new hire starts."


def _interview_with_quote(runner: CliRunner, db: str) -> tuple[str, str]:
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
    backend = LocalBackend(db_path=db)
    quote_id = backend.call("add_quote", {"interview_id": interview_id, "text": QUOTE})["id"]
    return interview_id, quote_id


def test_extract_then_list_and_get(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    interview_id, quote_id = _interview_with_quote(runner, db)

    extracted = runner.invoke(app, ["--db", db, "interviews", "extract", quote_id, "--json"])
    assert extracted.exit_code == 0, extracted.output
    candidates = json.loads(extracted.output)
    assert candidates

    listed = runner.invoke(
        app, ["--db", db, "candidates", "list", "--interview-id", interview_id, "--json"]
    )
    assert len(json.loads(listed.output)) == len(candidates)

    candidate_id = candidates[0]["id"]
    fetched = runner.invoke(app, ["--db", db, "candidates", "get", candidate_id, "--json"])
    assert json.loads(fetched.output)["id"] == candidate_id


def test_extract_is_idempotent(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    _, quote_id = _interview_with_quote(runner, db)

    runner.invoke(app, ["--db", db, "interviews", "extract", quote_id, "--json"])
    second = runner.invoke(app, ["--db", db, "interviews", "extract", quote_id, "--json"])
    assert json.loads(second.output) == []


def test_list_filters_by_status(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    _, quote_id = _interview_with_quote(runner, db)
    runner.invoke(app, ["--db", db, "interviews", "extract", quote_id, "--json"])

    proposed = runner.invoke(
        app, ["--db", db, "candidates", "list", "--status", "proposed", "--json"]
    )
    assert all(c["status"] == "proposed" for c in json.loads(proposed.output))


def test_delete_candidate(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    _, quote_id = _interview_with_quote(runner, db)
    candidate_id = json.loads(
        runner.invoke(app, ["--db", db, "interviews", "extract", quote_id, "--json"]).output
    )[0]["id"]

    deleted = runner.invoke(app, ["--db", db, "candidates", "delete", candidate_id, "-y"])
    assert deleted.exit_code == 0
    assert "Deleted outcome candidate" in deleted.output

    missing = runner.invoke(app, ["--db", db, "candidates", "get", candidate_id])
    assert missing.exit_code != 0
    assert "not found" in missing.output.lower()


def test_extract_unknown_quote_reports_not_found(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    result = runner.invoke(app, ["--db", db, "interviews", "extract", "missing"])
    assert result.exit_code != 0
    assert "not found" in result.output.lower()


def _first_proposed(runner: CliRunner, db: str) -> str:
    _, quote_id = _interview_with_quote(runner, db)
    runner.invoke(app, ["--db", db, "interviews", "extract", quote_id, "--json"])
    listed = runner.invoke(
        app, ["--db", db, "candidates", "list", "--status", "proposed", "--json"]
    )
    return json.loads(listed.output)[0]["id"]


def test_accept_candidate_prints_the_outcome_and_evidence(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    candidate_id = _first_proposed(runner, db)

    accepted = runner.invoke(
        app,
        [
            "--db",
            db,
            "candidates",
            "accept",
            candidate_id,
            "--importance",
            "8",
            "--satisfaction",
            "3",
            "--json",
        ],
    )

    assert accepted.exit_code == 0, accepted.output
    payload = json.loads(accepted.output)
    assert payload["candidate"]["status"] == "accepted"
    assert payload["outcome"]["statement"]
    assert payload["evidence"]["content"] == QUOTE


def test_accept_candidate_twice_keeps_one_outcome(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    candidate_id = _first_proposed(runner, db)
    args = [
        "--db",
        db,
        "candidates",
        "accept",
        candidate_id,
        "--importance",
        "8",
        "--satisfaction",
        "3",
        "--json",
    ]

    first = json.loads(runner.invoke(app, args).output)
    second = json.loads(runner.invoke(app, args).output)

    assert first["outcome"]["id"] == second["outcome"]["id"]
    outcomes = runner.invoke(
        app,
        ["--db", db, "desired-outcomes", "list", "--job-id", first["outcome"]["job_id"], "--json"],
    )
    assert len(json.loads(outcomes.output)) == 1


def test_reject_candidate_keeps_the_reason(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    candidate_id = _first_proposed(runner, db)

    rejected = runner.invoke(
        app,
        ["--db", db, "candidates", "reject", candidate_id, "--reason", "not a need", "--json"],
    )

    assert rejected.exit_code == 0, rejected.output
    assert json.loads(rejected.output)["decision_reason"] == "not a need"


def test_reject_candidate_without_a_reason_fails(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    candidate_id = _first_proposed(runner, db)

    result = runner.invoke(app, ["--db", db, "candidates", "reject", candidate_id, "--reason", " "])

    assert result.exit_code != 0
    assert "reason is required" in result.output.lower()


PARAPHRASE_QUOTES = [
    "Onboarding takes too long when a new hire starts.",
    "Onboarding takes too long when a new hire joins.",
    "Onboarding takes too long when a new hire arrives.",
    "Onboarding takes too long when a new hire begins.",
    "Onboarding takes too long when a new hire is hired.",
]


def _paraphrase_candidates(runner: CliRunner, db: str) -> list[dict]:
    """One interview with five paraphrased quotes, one candidate each."""
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
    backend = LocalBackend(db_path=db)
    candidates: list[dict] = []
    for text in PARAPHRASE_QUOTES:
        quote_id = backend.call("add_quote", {"interview_id": interview_id, "text": text})["id"]
        candidates.extend(backend.call("extract_candidates", {"quote_id": quote_id}))
    return candidates


def test_duplicates_groups_paraphrases_without_writing(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    candidates = _paraphrase_candidates(runner, db)

    before = runner.invoke(app, ["--db", db, "candidates", "list", "--json"])
    result = runner.invoke(app, ["--db", db, "candidates", "duplicates", "--json"])
    after = runner.invoke(app, ["--db", db, "candidates", "list", "--json"])

    assert result.exit_code == 0, result.output
    groups = json.loads(result.output)["groups"]
    assert len(groups) == 1
    assert sorted(groups[0]) == sorted(c["id"] for c in candidates)
    assert json.loads(before.output) == json.loads(after.output)


def test_merge_absorbs_evidence_into_one_outcome(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    candidates = _paraphrase_candidates(runner, db)
    accepted = json.loads(
        runner.invoke(
            app,
            [
                "--db",
                db,
                "candidates",
                "accept",
                candidates[0]["id"],
                "--importance",
                "8",
                "--satisfaction",
                "3",
                "--json",
            ],
        ).output
    )
    outcome_id = accepted["outcome"]["id"]
    merged_ids = [c["id"] for c in candidates[1:]]

    merged = runner.invoke(
        app,
        ["--db", db, "candidates", "merge", outcome_id, *merged_ids, "--json"],
    )

    assert merged.exit_code == 0, merged.output
    payload = json.loads(merged.output)
    assert payload["outcome"]["id"] == outcome_id
    assert [c["status"] for c in payload["merged"]] == ["merged"] * len(merged_ids)

    evidence = runner.invoke(
        app, ["--db", db, "evidence", "list", "--outcome-id", outcome_id, "--json"]
    )
    outcomes = runner.invoke(
        app,
        [
            "--db",
            db,
            "desired-outcomes",
            "list",
            "--job-id",
            accepted["outcome"]["job_id"],
            "--json",
        ],
    )
    assert len(json.loads(outcomes.output)) == 1
    assert len(json.loads(evidence.output)) == 5


def test_merge_is_idempotent(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    candidates = _paraphrase_candidates(runner, db)
    accepted = json.loads(
        runner.invoke(
            app,
            [
                "--db",
                db,
                "candidates",
                "accept",
                candidates[0]["id"],
                "--importance",
                "8",
                "--satisfaction",
                "3",
                "--json",
            ],
        ).output
    )
    outcome_id = accepted["outcome"]["id"]
    args = [
        "--db",
        db,
        "candidates",
        "merge",
        outcome_id,
        *[c["id"] for c in candidates[1:]],
        "--json",
    ]

    runner.invoke(app, args)
    second = json.loads(runner.invoke(app, args).output)

    assert second["evidence"] == []
    assert second["merged"] == []


def test_merge_into_unknown_outcome_fails(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    candidates = _paraphrase_candidates(runner, db)

    result = runner.invoke(
        app, ["--db", db, "candidates", "merge", "no-such-outcome", candidates[0]["id"]]
    )

    assert result.exit_code != 0
