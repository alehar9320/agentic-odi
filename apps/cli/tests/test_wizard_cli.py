"""Tests for the interactive ODI entity creation wizard command."""

from __future__ import annotations

import json
import re

from agentic_odi_cli.cli import app
from typer.testing import CliRunner

ANSI = re.compile(r"\x1b\[[0-9;]*m")
runner = CliRunner()


def _strip(text: str) -> str:
    return ANSI.sub("", text)


def test_wizard_full_flow_success(tmp_path):
    db = str(tmp_path / "odi.db")
    # Inputs:
    # 1. Job name ("Onboarding Workflow")
    # 2. Job description ("Guide new users")
    # 3. Step 1 name ("Prepare Profile")
    # 4. Step 1 order ("1")
    # 5. Add another step? ("n")
    # 6. Outcome statement ("Minimize setup duration")
    # 7. Direction ("minimize")
    # 8. Unit ("minutes")
    # 9. Object ("setup execution")
    # 10. Importance ("8.0")
    # 11. Satisfaction ("2.0")  -> Opportunity score: 8 + (8-2) = 14.00
    # 12. Category ("cost_reduction")
    # 13. Business statement ("Saves support time")
    # 14. Add another outcome? ("n")
    # 15. Commit this job to store? ("y")
    inputs = [
        "Onboarding Workflow",
        "Guide new users",
        "Prepare Profile",
        "1",
        "n",
        "Minimize setup duration",
        "minimize",
        "minutes",
        "setup execution",
        "8.0",
        "2.0",
        "cost_reduction",
        "Saves support time",
        "n",
        "y",
    ]
    user_input = "\n".join(inputs) + "\n"

    result = runner.invoke(app, ["--backend", "local", "--db", db, "wizard"], input=user_input)
    assert result.exit_code == 0, result.output
    output = _strip(result.output)

    assert "Welcome to the Agentic ODI Entity Creation Wizard!" in output
    assert "Opportunity score: 14.00" in output
    assert "Successfully created Job" in output

    # Verify Job in store
    jobs_res = runner.invoke(app, ["--backend", "local", "--db", db, "jobs", "list", "--json"])
    assert jobs_res.exit_code == 0
    jobs = json.loads(jobs_res.output)
    assert len(jobs) == 1
    job_id = jobs[0]["id"]
    assert jobs[0]["name"] == "Onboarding Workflow"
    assert jobs[0]["description"] == "Guide new users"

    # Verify Step in store
    steps_res = runner.invoke(
        app, ["--backend", "local", "--db", db, "steps", "list", "--job-id", job_id, "--json"]
    )
    assert steps_res.exit_code == 0
    steps = json.loads(steps_res.output)
    assert len(steps) == 1
    assert steps[0]["name"] == "Prepare Profile"
    assert steps[0]["order"] == 1

    # Verify Outcome in store
    outcomes_res = runner.invoke(
        app,
        [
            "--backend",
            "local",
            "--db",
            db,
            "customer-outcomes",
            "list",
            "--job-id",
            job_id,
            "--json",
        ],
    )
    assert outcomes_res.exit_code == 0
    outcomes = json.loads(outcomes_res.output)
    assert len(outcomes) == 1
    assert outcomes[0]["customer_value"]["statement"] == "Minimize setup duration"
    assert outcomes[0]["customer_value"]["importance"] == 8.0
    assert outcomes[0]["customer_value"]["satisfaction"] == 2.0
    assert outcomes[0]["opportunity_score"] == 14.0
    assert outcomes[0]["step_id"] == steps[0]["id"]


def test_wizard_decline_commit(tmp_path):
    db = str(tmp_path / "odi.db")
    inputs = [
        "Unsaved Job",
        "",
        "Step 1",
        "1",
        "n",
        "Minimize setup duration",
        "minimize",
        "minutes",
        "setup execution",
        "7.0",
        "5.0",
        "operational_efficiency",
        "Improves speed",
        "n",
        "n",  # Decline commit
    ]
    user_input = "\n".join(inputs) + "\n"

    result = runner.invoke(app, ["--backend", "local", "--db", db, "wizard"], input=user_input)
    assert result.exit_code == 0, result.output
    output = _strip(result.output)

    assert "Wizard cancelled. Job was not committed." in output

    jobs_res = runner.invoke(app, ["--backend", "local", "--db", db, "jobs", "list", "--json"])
    assert json.loads(jobs_res.output) == []


def test_wizard_input_validation_and_retry(tmp_path):
    db = str(tmp_path / "odi.db")
    inputs = [
        "Valid Job",
        "Description",
        "Step 1",
        "invalid_order",  # Invalid int -> triggers retry
        "1",  # Valid int
        "n",
        "Minimize errors",
        "minimize",
        "count",
        "errors",
        "15.0",  # Invalid importance -> > 10.0
        "8.0",  # Valid importance
        "-2.0",  # Invalid satisfaction -> < 1.0
        "3.0",  # Valid satisfaction
        "risk_mitigation",
        "Reduces risks",
        "n",
        "y",
    ]
    user_input = "\n".join(inputs) + "\n"

    result = runner.invoke(app, ["--backend", "local", "--db", db, "wizard"], input=user_input)
    assert result.exit_code == 0, result.output
    output = _strip(result.output)

    assert "Please enter a valid integer for step order." in output
    assert "Importance score must be between 1.0 and 10.0." in output
    assert "Satisfaction score must be between 1.0 and 10.0." in output
    assert "Successfully created Job" in output


def test_wizard_multiple_steps_and_outcomes(tmp_path):
    db = str(tmp_path / "odi.db")
    inputs = [
        "Multi Job",
        "Multi Description",
        # Step 1
        "Step One",
        "1",
        "y",  # Add another step
        # Step 2
        "Step Two",
        "2",
        "n",
        # Outcome 1
        "Outcome One",
        "minimize",
        "minutes",
        "process",
        "9.0",
        "2.0",
        "revenue_growth",
        "Growth statement",
        "y",  # Add another outcome
        # Outcome 2
        "Outcome Two",
        "maximize",
        "quality",
        "output",
        "8.5",
        "4.0",
        "retention",
        "Retention statement",
        "n",
        "y",  # Commit
    ]
    user_input = "\n".join(inputs) + "\n"

    result = runner.invoke(app, ["--backend", "local", "--db", db, "wizard"], input=user_input)
    assert result.exit_code == 0, result.output

    jobs = json.loads(
        runner.invoke(app, ["--backend", "local", "--db", db, "jobs", "list", "--json"]).output
    )
    job_id = jobs[0]["id"]

    steps = json.loads(
        runner.invoke(
            app, ["--backend", "local", "--db", db, "steps", "list", "--job-id", job_id, "--json"]
        ).output
    )
    assert len(steps) == 2
    assert [s["name"] for s in steps] == ["Step One", "Step Two"]

    outcomes = json.loads(
        runner.invoke(
            app,
            [
                "--backend",
                "local",
                "--db",
                db,
                "customer-outcomes",
                "list",
                "--job-id",
                job_id,
                "--json",
            ],
        ).output
    )
    assert len(outcomes) == 2
    statements = [o["customer_value"]["statement"] for o in outcomes]
    assert statements == ["Outcome One", "Outcome Two"]
