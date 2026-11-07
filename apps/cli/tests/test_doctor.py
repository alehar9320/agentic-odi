import json
import socket
from pathlib import Path

import pytest
from agentic_odi_cli import doctor
from agentic_odi_cli.cli import app
from agentic_odi_cli.doctor import (
    Check,
    Report,
    _redact,
    check_db_integrity,
    check_db_path,
    find_repo_root,
    run_doctor,
)
from typer.testing import CliRunner

runner = CliRunner()


def _checks(report: Report) -> dict[str, Check]:
    return {check.id: check for check in report.checks}


def test_json_is_one_object_with_the_documented_shape(monkeypatch):
    monkeypatch.setattr(socket, "create_connection", _refuse)
    result = runner.invoke(app, ["doctor", "--json", "--offline"])

    body = json.loads(result.stdout)
    assert body["schema_version"] == 1
    assert set(body) == {
        "schema_version",
        "generated_at",
        "ok",
        "exit_code",
        "environment",
        "checks",
    }
    assert set(body["environment"]) >= {"platform", "python", "cli_version", "commit"}
    assert result.stderr == ""
    for check in body["checks"]:
        assert set(check) >= {"id", "status", "summary", "detail"}
        assert check["status"] in doctor.STATUSES
    assert body["exit_code"] == result.exit_code


def test_a_closed_studio_port_fails_and_explains_what_to_try(monkeypatch):
    monkeypatch.setattr(socket, "create_connection", _refuse)
    result = runner.invoke(app, ["doctor", "--offline"])

    assert result.exit_code == 1
    assert "FAIL port.studio" in result.stdout
    assert "What to try:" in result.stdout
    assert "agentic_odi_studio_api.main" in result.stdout


def test_a_missing_database_warns_and_skips_integrity(monkeypatch, tmp_path):
    monkeypatch.setenv("AGENTIC_ODI_DB", str(tmp_path / "odi.db"))

    path_check = check_db_path()
    integrity = check_db_integrity()

    assert path_check.status == "warn"
    assert integrity.status == "skip"
    assert not (tmp_path / "odi.db").exists()


def test_offline_skips_the_model_probe(monkeypatch):
    monkeypatch.setattr(socket, "create_connection", _refuse)
    report = run_doctor(offline=True, timeout=0.01)

    assert _checks(report)["llm.endpoint"].status == "skip"


def test_integrity_reports_a_corrupt_file_as_fail(monkeypatch, tmp_path):
    broken = tmp_path / "odi.db"
    broken.write_bytes(b"this is not sqlite")
    monkeypatch.setenv("AGENTIC_ODI_DB", str(broken))

    check = check_db_integrity()
    assert check.status == "fail"


def test_api_key_never_appears_and_url_userinfo_is_redacted(monkeypatch):
    secret = "sk-live-do-not-print"
    monkeypatch.setenv("AGENTIC_ODI_API_KEY", secret)
    monkeypatch.setattr(socket, "create_connection", _refuse)

    result = runner.invoke(app, ["doctor", "--json", "--offline"])

    assert secret not in result.stdout
    assert secret not in result.stderr
    assert "user" not in _redact("https://user:pass@example.com/mcp")
    assert "pass" not in _redact("https://user:pass@example.com/mcp")


def test_unknown_flag_is_a_usage_error():
    result = runner.invoke(app, ["doctor", "--nonsense"])
    assert result.exit_code == 2


def test_the_report_names_every_check_once(monkeypatch):
    monkeypatch.setattr(socket, "create_connection", _refuse)
    report = run_doctor(offline=True, timeout=0.01)
    ids = [check.id for check in report.checks]

    assert len(ids) == len(set(ids))
    assert set(ids) == {
        "cli.version",
        "versions.parity",
        "python.version",
        "uv.present",
        "workspace.root",
        "spa.build",
        "db.path",
        "db.integrity",
        "port.studio",
        "studio.api",
        "mcp.endpoint",
        "llm.endpoint",
        "connectors.config",
        "paths.writable",
    }


def test_repo_root_honours_the_override(monkeypatch, tmp_path):
    monkeypatch.setenv("AGENTIC_ODI_REPO_ROOT", str(tmp_path))
    assert find_repo_root() == tmp_path


def test_repo_root_is_none_when_no_packages_exist(monkeypatch, tmp_path):
    monkeypatch.delenv("AGENTIC_ODI_REPO_ROOT", raising=False)
    monkeypatch.chdir(tmp_path)
    assert find_repo_root(Path(tmp_path)) is None


def _refuse(*_args, **_kwargs):
    raise ConnectionRefusedError("refused")


@pytest.mark.parametrize("status", ["pass", "warn", "fail", "skip"])
def test_only_fail_changes_the_exit_code(status):
    report = Report(checks=[Check("x", status, "summary")])
    assert report.exit_code == (1 if status == "fail" else 0)
