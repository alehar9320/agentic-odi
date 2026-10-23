from agentic_odi_cli.cli import app
from typer.testing import CliRunner

runner = CliRunner()


def test_schedule_cli_crud(tmp_path, monkeypatch):
    db_file = str(tmp_path / "test_odi.db")
    monkeypatch.setenv("AGENTIC_ODI_DB", db_file)

    # Create task
    res = runner.invoke(app, ["schedule", "create", "-n", "Test Task", "-e", "+1h"])
    assert res.exit_code == 0
    assert "Scheduled work created successfully with ID:" in res.stdout

    # List tasks
    res_list = runner.invoke(app, ["schedule", "list", "--json"])
    assert res_list.exit_code == 0
    assert "Test Task" in res_list.stdout

    import json

    data = json.loads(res_list.stdout)
    assert len(data) == 1
    work_id = data[0]["id"]

    # Show task
    res_show = runner.invoke(app, ["schedule", "show", work_id])
    assert res_show.exit_code == 0
    assert work_id in res_show.stdout

    # Trigger task
    res_trig = runner.invoke(app, ["schedule", "trigger", work_id])
    assert res_trig.exit_code == 0
    assert "Triggered task 'Test Task'" in res_trig.stdout

    # Cancel task
    res_canc = runner.invoke(app, ["schedule", "cancel", work_id])
    assert res_canc.exit_code == 0
    assert "Cancelled scheduled task" in res_canc.stdout
