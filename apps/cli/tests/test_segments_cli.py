"""Tests for the segments and strategy CLI groups (Stages 5 and 6).

The seed is deliberately small and realistic: one job with two steps, two
underserved outcomes on the first step, one served outcome on the second, and
one outcome that attaches to no step. That gives the clusterer exactly one
segment, leaves the rest unclustered, and leaves the job with a served outcome
so the differentiated path has the evidence Stage 6 requires.
"""

from __future__ import annotations

import json

from agentic_odi_cli.cli import app
from typer.testing import CliRunner

#: An outcome whose opportunity score is 9 + max(9 - 2, 0) = 16, above the > 10
#: underserved line.
UNDERSERVED = (
    "Minimize the time it takes to match a line to a purchase order when the invoice arrives",
    9,
    2,
)
UNDERSERVED_TOO = (
    "Minimize the number of lines that need a manual review while reconciling an invoice",
    8,
    1,
)
#: 5 + max(5 - 7, 0) = 5: the market already gets this one.
SERVED = (
    "Minimize the time it takes to file the reconciled record after the match is complete",
    5,
    7,
)
#: One outcome with no step: too few to be a segment, so it stays unclustered.
ORPHAN = (
    "Minimize the time it takes to explain a variance to an auditor during a review",
    7,
    3,
)


def _json(runner: CliRunner, args: list[str]) -> object:
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


def _add_outcome(
    runner: CliRunner,
    db: str,
    job_id: str,
    outcome: tuple[str, int, int],
    step_id: str | None = None,
) -> str:
    statement, importance, satisfaction = outcome
    args = [
        "--db",
        db,
        "desired-outcomes",
        "add",
        "--job-id",
        job_id,
        "--statement",
        statement,
        "--importance",
        str(importance),
        "--satisfaction",
        str(satisfaction),
        "--json",
    ]
    if step_id is not None:
        args.extend(["--step-id", step_id])
    return str(_json(runner, args)["id"])  # type: ignore[index]


def _seed(tmp_path) -> tuple[str, str]:
    """A job with one underserved step, one served step, and one orphan outcome."""
    db = str(tmp_path / "odi.db")
    runner = CliRunner()

    job = _json(
        runner,
        [
            "--db",
            db,
            "jobs",
            "add",
            "--name",
            "Reconcile invoices",
            "--description",
            "Reconcile invoices without manual effort",
            "--json",
        ],
    )
    job_id = str(job["id"])  # type: ignore[index]

    match = _json(
        runner,
        [
            "--db",
            db,
            "steps",
            "add",
            "--job-id",
            job_id,
            "--name",
            "Match each line",
            "--order",
            "1",
            "--allow-empty-job-map",
            "--json",
        ],
    )
    match_id = str(match["id"])  # type: ignore[index]

    _add_outcome(runner, db, job_id, UNDERSERVED, match_id)
    _add_outcome(runner, db, job_id, UNDERSERVED_TOO, match_id)

    file_step = _json(
        runner,
        [
            "--db",
            db,
            "steps",
            "add",
            "--job-id",
            job_id,
            "--name",
            "File the record",
            "--order",
            "2",
            "--json",
        ],
    )
    _add_outcome(runner, db, job_id, SERVED, str(file_step["id"]))  # type: ignore[index]
    _add_outcome(runner, db, job_id, ORPHAN)

    return db, job_id


def _segment_id(runner: CliRunner, db: str) -> str:
    segments = _json(runner, ["--db", db, "segments", "list", "--json"])
    assert isinstance(segments, list) and segments
    return str(segments[0]["id"])


def test_nothing_is_a_segment_until_segment_market_runs(tmp_path):
    db, _ = _seed(tmp_path)
    runner = CliRunner()

    listed = runner.invoke(app, ["--db", db, "segments", "list"])
    assert listed.exit_code == 0, listed.output
    assert "No segments yet" in listed.output
    assert "odi segments run" in listed.output


def test_segments_run_clusters_by_step_and_keeps_the_lone_outcome_visible(tmp_path):
    db, job_id = _seed(tmp_path)
    runner = CliRunner()

    result = runner.invoke(
        app, ["--db", db, "segments", "run", "--job", job_id, "--people", "Finance leads"]
    )
    assert result.exit_code == 0, result.output

    # One segment on "Match each line"; the served and orphan outcomes stay out.
    segments = _json(runner, ["--db", db, "segments", "list", "--json"])
    assert isinstance(segments, list)
    assert len(segments) == 1
    segment = segments[0]
    assert segment["people"] == "Finance leads"
    assert segment["people_inferred"] is False
    assert segment["verdict"] == "underserved"
    assert segment["name"] == "Finance leads, Match each line"
    assert len(segment["outcome_ids"]) == 2
    # Confidence carries the verdict: 2 of 4 outcomes, 2 of 4 toward full evidence.
    assert segment["confidence"] == 0.5
    assert "underserved" in segment["rationale"]

    human = runner.invoke(app, ["--db", db, "segments", "list"])
    assert human.exit_code == 0, human.output
    assert "Finance leads" in human.output
    assert "underserved (confidence 0.50)" in human.output


def test_segments_show_names_the_evidence_behind_the_verdict(tmp_path):
    db, job_id = _seed(tmp_path)
    runner = CliRunner()
    runner.invoke(app, ["--db", db, "segments", "run", "--job", job_id])
    segment_id = _segment_id(runner, db)

    shown = runner.invoke(app, ["--db", db, "segments", "show", segment_id])
    assert shown.exit_code == 0, shown.output
    assert "Match each line" in shown.output
    assert "2 outcomes" in shown.output
    assert "underserved (confidence" in shown.output

    as_json = _json(runner, ["--db", db, "segments", "show", segment_id, "--json"])
    assert as_json["id"] == segment_id  # type: ignore[index]


def test_segments_show_refuses_an_unknown_id(tmp_path):
    db, _ = _seed(tmp_path)
    runner = CliRunner()
    runner.invoke(app, ["--db", db, "segments", "run"])

    missing = runner.invoke(app, ["--db", db, "segments", "show", "not-a-segment"])
    assert missing.exit_code != 0
    assert "Segment not found: not-a-segment" in missing.output


def test_segments_run_refuses_an_unknown_job(tmp_path):
    db, _ = _seed(tmp_path)
    runner = CliRunner()

    missing = runner.invoke(app, ["--db", db, "segments", "run", "--job", "not-a-job"])
    assert missing.exit_code == 1
    assert "Job not found: not-a-job" in missing.output


def test_strategy_propose_names_one_path_and_the_two_it_beat(tmp_path):
    db, job_id = _seed(tmp_path)
    runner = CliRunner()
    runner.invoke(app, ["--db", db, "segments", "run", "--job", job_id])

    proposed = runner.invoke(app, ["--db", db, "strategy", "propose", "--job", job_id])
    assert proposed.exit_code == 0, proposed.output
    assert "Paths this one beat:" in proposed.output

    strategy = _json(runner, ["--db", db, "strategy", "show", "--json"])
    assert strategy is not None
    assert strategy["kind"] == "differentiated"  # type: ignore[index]
    assert strategy["segment_id"] == _segment_id(runner, db)  # type: ignore[index]
    rejected = {item["kind"] for item in strategy["rejected"]}  # type: ignore[index]
    assert rejected == {"disruptive", "new_market"}
    assert all(item["why"] for item in strategy["rejected"])  # type: ignore[index]

    human = runner.invoke(app, ["--db", db, "strategy", "show"])
    assert human.exit_code == 0, human.output
    assert "differentiated" in human.output


def test_strategy_show_is_honest_when_nothing_has_been_proposed(tmp_path):
    db, _ = _seed(tmp_path)
    runner = CliRunner()

    shown = runner.invoke(app, ["--db", db, "strategy", "show"])
    assert shown.exit_code == 0, shown.output
    assert "No strategy recorded" in shown.output

    assert _json(runner, ["--db", db, "strategy", "show", "--json"]) is None


def test_strategy_propose_refuses_to_invent_a_bet(tmp_path):
    db = str(tmp_path / "empty.db")
    runner = CliRunner()
    _json(runner, ["--db", db, "jobs", "add", "--name", "An unexamined job", "--json"])

    proposed = runner.invoke(app, ["--db", db, "strategy", "propose"])
    assert proposed.exit_code == 1
    assert "No path is supported yet" in proposed.output


def test_segments_resolve_through_the_backend_seam(monkeypatch):
    """The groups must go through ``run_tool`` like every other command."""
    from agentic_odi_cli import backend as backend_module

    calls: list[tuple[str, dict]] = []
    segment = {
        "id": "seg-1",
        "name": "Finance leads, Match each line",
        "people": "Finance leads",
        "people_inferred": False,
        "job_statement": "Reconcile invoices",
        "verdict": "underserved",
        "confidence": 0.5,
        "outcome_ids": ["O-1", "O-2"],
        "rationale": "Two outcomes on Match each line; underserved.",
    }

    class _FakeBackend(backend_module.Backend):
        def call(self, tool_name: str, args: dict) -> object:
            calls.append((tool_name, args))
            if tool_name == "get_strategy":
                return None
            if tool_name == "propose_strategy":
                return {
                    "id": "str-1",
                    "kind": "differentiated",
                    "segment_id": "seg-1",
                    "thesis": "Match each line is underserved.",
                    "bets": ["Build against match each line"],
                    "rejected": [
                        {"kind": "disruptive", "why": "no segment is overserved"},
                        {"kind": "new_market", "why": "every outcome maps to a known job"},
                    ],
                }
            return [segment]

    monkeypatch.setattr(backend_module, "require_backend", lambda: _FakeBackend())

    runner = CliRunner()
    assert runner.invoke(app, ["segments", "run"]).exit_code == 0
    assert runner.invoke(app, ["segments", "list"]).exit_code == 0
    assert runner.invoke(app, ["segments", "show", "seg-1"]).exit_code == 0
    assert runner.invoke(app, ["strategy", "propose"]).exit_code == 0
    assert runner.invoke(app, ["strategy", "show"]).exit_code == 0

    assert [name for name, _ in calls] == [
        "segment_market",
        "get_segments",
        "get_segments",
        "propose_strategy",
        "get_strategy",
    ]
