import json

from typer.testing import CliRunner

from cli.cli import app


def _job_id(runner: CliRunner, db: str) -> str:
    result = runner.invoke(app, ["--db", db, "jobs", "add", "--name", "J", "--json"])
    assert result.exit_code == 0, result.output
    return json.loads(result.output)["id"]


def test_steps_add_and_list_job_map(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    job_id = _job_id(runner, db)

    add = runner.invoke(
        app,
        ["--db", db, "steps", "add", "--job-id", job_id, "--name", "S", "--order", "1"],
    )
    assert add.exit_code == 0 and "Step created" in add.output

    listed = runner.invoke(app, ["--db", db, "steps", "list", "--job-id", job_id])
    assert listed.exit_code == 0 and "S" in listed.output


def test_steps_full_lifecycle(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    job_id = _job_id(runner, db)
    added = runner.invoke(
        app,
        ["--db", db, "steps", "add", "--job-id", job_id, "--name", "S", "--order", "1", "--json"],
    )
    step_id = json.loads(added.output)["id"]

    fetched = runner.invoke(app, ["--db", db, "steps", "get", step_id, "--json"])
    assert fetched.exit_code == 0
    assert json.loads(fetched.output)["name"] == "S"

    updated = runner.invoke(app, ["--db", db, "steps", "update", step_id, "--name", "S2", "--json"])
    assert updated.exit_code == 0
    payload = json.loads(updated.output)
    assert payload["name"] == "S2"
    assert payload["order"] == 1

    deleted = runner.invoke(app, ["--db", db, "steps", "delete", step_id, "-y"])
    assert deleted.exit_code == 0 and "Deleted step" in deleted.output

    listed = runner.invoke(app, ["--db", db, "steps", "list", "--job-id", job_id, "--json"])
    assert json.loads(listed.output) == []


def test_steps_add_unknown_job_errors(tmp_path):
    result = CliRunner().invoke(
        app,
        [
            "--db",
            str(tmp_path / "odi.db"),
            "steps",
            "add",
            "--job-id",
            "nope",
            "--name",
            "S",
            "--order",
            "1",
        ],
    )

    assert result.exit_code == 1
    assert "Job not found: nope" in result.output
