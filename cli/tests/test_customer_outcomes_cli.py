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


def _add(db_path: str, *, alias: str = "customer-outcomes") -> list[str]:
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
