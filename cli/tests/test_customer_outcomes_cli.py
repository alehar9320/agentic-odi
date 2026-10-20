"""Customer Outcomes CLI: local backend, aliases, output, and errors."""

from __future__ import annotations

import json
import re

from typer.testing import CliRunner

from cli.cli import app

ANSI = re.compile(r"\x1b\[[0-9;]*m")
runner = CliRunner()


def _strip(text: str) -> str:
    return ANSI.sub("", text)


def _seed_parents(db_path: str) -> None:
    """Customer Outcomes validate their Job and Step, so seed both up front."""
    from core import Job, Step
    from core.sqlite_repository import SQLiteRepository

    repo = SQLiteRepository(db_path=db_path)
    if repo.get_job("job-1") is None:
        repo.add_job(Job(id="job-1", name="Onboard customers"))
    if repo.get_step("step-1") is None:
        repo.add_step(Step(id="step-1", job_id="job-1", name="Prepare", order=1))


def _add(db_path: str, *, alias: str = "customer-outcomes") -> list[str]:
    _seed_parents(db_path)
    return [
        "--backend",
        "local",
        "--db",
        db_path,
        alias,
        "add",
        "--job-id",
        "job-1",
        "--direction",
        "minimize",
        "--unit",
        "time",
        "--object",
        "to resolve setup errors",
        "--statement",
        "Minimize the time to resolve setup errors",
        "--importance",
        "8.8",
        "--satisfaction",
        "3.2",
        "--category",
        "cost_reduction",
        "--business-statement",
        "Saves engineering hours",
    ]


def test_help_lists_subcommands_and_alias(tmp_path):
    primary = runner.invoke(app, ["customer-outcomes", "--help"])
    alias = runner.invoke(app, ["outcomes", "--help"])
    for result in (primary, alias):
        assert result.exit_code == 0
        output = _strip(result.output)
        for command in ("add", "get", "list", "update", "delete", "score"):
            assert command in output


def test_local_add_then_get_then_list(tmp_path):
    db = str(tmp_path / "odi.db")
    added = runner.invoke(app, _add(db))
    assert added.exit_code == 0, added.output
    assert "Customer outcome created:" in _strip(added.output)

    listed = runner.invoke(app, ["--backend", "local", "--db", db, "customer-outcomes", "list"])
    assert listed.exit_code == 0
    output = _strip(listed.output)
    assert "statement" in output
    assert "Minimize the time to resolve setup errors" in output
    assert "8.8" in output

    outcome_id = json.loads(
        runner.invoke(
            app,
            ["--backend", "local", "--db", db, "customer-outcomes", "list", "--json"],
        ).output
    )[0]["id"]
    fetched = runner.invoke(
        app, ["--backend", "local", "--db", db, "customer-outcomes", "get", outcome_id]
    )
    assert fetched.exit_code == 0
    assert outcome_id in _strip(fetched.output)


def test_local_update_changes_business_statement(tmp_path):
    db = str(tmp_path / "odi.db")
    runner.invoke(app, _add(db))
    outcome_id = json.loads(
        runner.invoke(
            app, ["--backend", "local", "--db", db, "customer-outcomes", "list", "--json"]
        ).output
    )[0]["id"]

    updated = runner.invoke(
        app,
        [
            "--backend",
            "local",
            "--db",
            db,
            "customer-outcomes",
            "update",
            outcome_id,
            "--business-statement",
            "Reduces churn",
            "--importance",
            "9.5",
        ],
    )
    assert updated.exit_code == 0, updated.output

    fetched = json.loads(
        runner.invoke(
            app,
            ["--backend", "local", "--db", db, "customer-outcomes", "get", outcome_id, "--json"],
        ).output
    )
    assert fetched["business_value"]["statement"] == "Reduces churn"
    assert fetched["customer_value"]["importance"] == 9.5


def test_local_delete(tmp_path):
    db = str(tmp_path / "odi.db")
    runner.invoke(app, _add(db))
    outcome_id = json.loads(
        runner.invoke(
            app, ["--backend", "local", "--db", db, "customer-outcomes", "list", "--json"]
        ).output
    )[0]["id"]

    deleted = runner.invoke(
        app,
        ["--backend", "local", "--db", db, "customer-outcomes", "delete", outcome_id, "--yes"],
    )
    assert deleted.exit_code == 0
    assert "Deleted customer outcome" in _strip(deleted.output)


def test_list_empty_is_friendly_and_json_is_array(tmp_path):
    db = str(tmp_path / "odi.db")
    human = runner.invoke(app, ["--backend", "local", "--db", db, "customer-outcomes", "list"])
    assert human.exit_code == 0
    assert "No customer outcomes found." in _strip(human.output)

    machine = runner.invoke(
        app, ["--backend", "local", "--db", db, "customer-outcomes", "list", "--json"]
    )
    assert json.loads(machine.output) == []


def test_missing_outcome_reports_error_with_exit_1(tmp_path):
    db = str(tmp_path / "odi.db")
    result = runner.invoke(
        app, ["--backend", "local", "--db", db, "customer-outcomes", "get", "nope"]
    )
    assert result.exit_code == 1
    assert "Customer outcome not found: nope" in _strip(result.output)


def test_score_top_level_and_alias(tmp_path):
    top = runner.invoke(app, ["score", "8", "2"])
    assert top.exit_code == 0
    assert "Opportunity score: 14.00" in _strip(top.output)

    alias = runner.invoke(app, ["outcomes", "score", "8", "2"])
    assert alias.exit_code == 0
    assert "Opportunity score: 14.00" in _strip(alias.output)


def test_score_json(tmp_path):
    result = runner.invoke(app, ["score", "8", "2", "--json"])
    assert json.loads(result.output)["opportunity_score"] == 14.0


def test_add_stores_contextual_clarifier_and_step_id(tmp_path):
    db = str(tmp_path / "odi.db")
    result = runner.invoke(
        app,
        _add(db) + ["--contextual-clarifier", "on mobile", "--step-id", "step-1"],
    )

    assert result.exit_code == 0, result.output
    stored = json.loads(
        runner.invoke(
            app, ["--backend", "local", "--db", db, "customer-outcomes", "list", "--json"]
        ).output
    )[0]
    assert stored["customer_value"]["contextual_clarifier"] == "on mobile"
    assert stored["step_id"] == "step-1"


def test_list_filters_by_job_id(tmp_path):
    db = str(tmp_path / "odi.db")
    runner.invoke(app, _add(db))

    matching = runner.invoke(
        app,
        [
            "--backend",
            "local",
            "--db",
            db,
            "customer-outcomes",
            "list",
            "--job-id",
            "job-1",
            "--json",
        ],
    )
    missing = runner.invoke(
        app,
        [
            "--backend",
            "local",
            "--db",
            db,
            "customer-outcomes",
            "list",
            "--job-id",
            "other",
            "--json",
        ],
    )

    assert len(json.loads(matching.output)) == 1
    assert json.loads(missing.output) == []


def test_update_accepts_every_field(tmp_path):
    db = str(tmp_path / "odi.db")
    runner.invoke(app, _add(db))
    outcome_id = json.loads(
        runner.invoke(
            app, ["--backend", "local", "--db", db, "customer-outcomes", "list", "--json"]
        ).output
    )[0]["id"]

    result = runner.invoke(
        app,
        [
            "--backend",
            "local",
            "--db",
            db,
            "customer-outcomes",
            "update",
            outcome_id,
            "--step-id",
            "step-1",
            "--importance",
            "9",
            "--satisfaction",
            "2",
            "--direction",
            "maximize",
            "--unit-of-measure",
            "hours",
            "--object-of-control",
            "throughput",
            "--contextual-clarifier",
            "during onboarding",
            "--statement",
            "Maximize onboarding throughput",
            "--category",
            "retention",
            "--business-statement",
            "Keeps customers",
            "--detail",
            "Expansion revenue",
            "--estimated-annual-value",
            "120000",
            "--confidence",
            "0.8",
        ],
    )

    assert result.exit_code == 0, result.output
    stored = json.loads(
        runner.invoke(
            app,
            ["--backend", "local", "--db", db, "customer-outcomes", "get", outcome_id, "--json"],
        ).output
    )
    assert stored["step_id"] == "step-1"
    assert stored["customer_value"]["direction"] == "maximize"
    assert stored["customer_value"]["unit_of_measure"] == "hours"
    assert stored["customer_value"]["object_of_control"] == "throughput"
    assert stored["customer_value"]["contextual_clarifier"] == "during onboarding"
    assert stored["customer_value"]["statement"] == "Maximize onboarding throughput"
    assert stored["customer_value"]["importance"] == 9.0
    assert stored["customer_value"]["satisfaction"] == 2.0
    assert stored["business_value"]["category"] == "retention"
    assert stored["business_value"]["statement"] == "Keeps customers"
    assert stored["business_value"]["detail"] == "Expansion revenue"
    assert stored["business_value"]["estimated_annual_value"] == 120000.0
    assert stored["business_value"]["confidence"] == 0.8


def test_delete_confirmation_can_abort_or_proceed(tmp_path):
    db = str(tmp_path / "odi.db")
    runner.invoke(app, _add(db))
    outcome_id = json.loads(
        runner.invoke(
            app, ["--backend", "local", "--db", db, "customer-outcomes", "list", "--json"]
        ).output
    )[0]["id"]
    delete_args = ["--backend", "local", "--db", db, "customer-outcomes", "delete", outcome_id]

    aborted = runner.invoke(app, delete_args, input="n\n")
    still_there = runner.invoke(
        app, ["--backend", "local", "--db", db, "customer-outcomes", "list", "--json"]
    )
    confirmed = runner.invoke(app, delete_args, input="y\n")

    assert aborted.exit_code == 0
    assert len(json.loads(still_there.output)) == 1
    assert confirmed.exit_code == 0
    assert "Deleted customer outcome" in _strip(confirmed.output)


_METRIC = (
    '{"name":"m","direction":"maximize","unit_of_measure":"s","importance":8,"satisfaction":3}'
)


def test_customer_outcome_add_with_value_metrics(tmp_path):
    db = str(tmp_path / "odi.db")
    result = runner.invoke(app, [*_add(db), "--value-metric", _METRIC, "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["customer_value"]["value_metrics"][0]["name"] == "m"


def test_customer_outcome_add_rejects_bad_metric_json(tmp_path):
    db = str(tmp_path / "odi.db")
    result = runner.invoke(app, [*_add(db), "--value-metric", "not-json"])

    assert result.exit_code != 0
    # Highlighted terminals (e.g. CI) split option tokens with ANSI codes, so
    # strip styling before matching on the option name.
    assert "value-metric" in _strip(result.output).lower()


def test_customer_outcome_update_replaces_value_metrics(tmp_path):
    db = str(tmp_path / "odi.db")
    created = runner.invoke(app, [*_add(db), "--value-metric", _METRIC, "--json"])
    outcome_id = json.loads(created.output)["id"]
    replacement = (
        '{"name":"m2","direction":"maximize","unit_of_measure":"s","importance":9,"satisfaction":3}'
    )

    updated = runner.invoke(
        app,
        [
            "--backend",
            "local",
            "--db",
            db,
            "customer-outcomes",
            "update",
            outcome_id,
            "--value-metric",
            replacement,
            "--json",
        ],
    )

    assert updated.exit_code == 0, updated.output
    payload = json.loads(updated.output)
    names = [metric["name"] for metric in payload["customer_value"]["value_metrics"]]
    assert names == ["m2"]
