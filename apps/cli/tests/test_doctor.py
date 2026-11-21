"""`odi doctor` explains why the Studio will not start, and never changes the machine."""

import json
import socket
import sqlite3
from pathlib import Path

import pytest
import typer
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


def test_cli_version_passes_for_a_release_build(monkeypatch):
    monkeypatch.setattr(doctor.version, "COMMIT", "abc1234")
    assert doctor.check_cli_version().status == "pass"


def test_versions_parity_passes_when_the_three_packages_agree(monkeypatch):
    monkeypatch.setattr(doctor.importlib.metadata, "version", lambda name: "0.15.0")

    check = doctor.check_versions_parity()

    assert (check.status, check.summary) == ("pass", "CLI, MCP server and sidecar all 0.15.0")


def test_versions_parity_fails_when_the_packages_disagree(monkeypatch):
    installed = {
        "agentic-odi-cli": "0.15.0",
        "agentic-odi-mcp-server": "0.15.0",
        "agentic-odi-studio-api": "0.14.0",
    }
    monkeypatch.setattr(doctor.importlib.metadata, "version", installed.__getitem__)

    check = doctor.check_versions_parity()

    assert check.status == "fail"
    assert "agentic-odi-studio-api 0.14.0" in check.detail
    assert check.remedy is not None


def test_versions_parity_skips_when_the_metadata_is_missing(monkeypatch):
    def missing(name):
        raise doctor.importlib.metadata.PackageNotFoundError(name)

    monkeypatch.setattr(doctor.importlib.metadata, "version", missing)

    check = doctor.check_versions_parity()

    assert check.status == "skip"
    assert "none" in check.detail


def test_python_version_fails_below_three_ten(monkeypatch):
    monkeypatch.setattr(doctor.platform, "python_version_tuple", lambda: ("3", "9", "18"))
    monkeypatch.setattr(doctor.sys, "version", "3.9.18 (main)")

    check = doctor.check_python_version()

    assert check.status == "fail"
    assert check.detail == "3.9.18"
    assert check.remedy is not None


def test_uv_is_skipped_in_a_frozen_build(monkeypatch):
    monkeypatch.setattr(doctor.paths, "is_frozen", lambda: True)
    assert doctor.check_uv().status == "skip"


def test_uv_missing_from_path_is_a_failure(monkeypatch):
    monkeypatch.setattr(doctor.paths, "is_frozen", lambda: False)
    monkeypatch.setattr(doctor.shutil, "which", lambda name: None)

    check = doctor.check_uv()

    assert check.status == "fail"
    assert check.remedy is not None


def test_workspace_root_warns_without_a_root_and_passes_with_one(monkeypatch, tmp_path):
    monkeypatch.setattr(doctor.paths, "repo_root_override", lambda: None)
    monkeypatch.chdir(tmp_path)
    assert doctor.check_workspace_root().status == "warn"

    (tmp_path / "apps" / "mcp-server").mkdir(parents=True)
    (tmp_path / "apps" / "studio-api").mkdir(parents=True)

    passed = doctor.check_workspace_root()

    assert passed.status == "pass"
    assert passed.summary == str(tmp_path.resolve())


def test_spa_build_skips_without_a_root_and_reports_the_missing_build(monkeypatch, tmp_path):
    monkeypatch.setattr(doctor.paths, "repo_root_override", lambda: None)
    monkeypatch.chdir(tmp_path)
    assert doctor.check_spa_build().status == "skip"

    monkeypatch.setattr(doctor.paths, "repo_root_override", lambda: tmp_path)
    warned = doctor.check_spa_build()
    assert warned.status == "warn"
    assert warned.remedy is not None

    index = tmp_path / "apps" / "studio" / "dist" / "index.html"
    index.parent.mkdir(parents=True)
    index.write_text("<html></html>", encoding="utf-8")
    assert doctor.check_spa_build().status == "pass"


def test_db_path_skips_an_in_memory_store(monkeypatch):
    monkeypatch.setenv("AGENTIC_ODI_DB", ":memory:")
    assert doctor.check_db_path().status == "skip"


def test_db_path_fails_when_the_directory_is_not_writable(monkeypatch, tmp_path):
    database = tmp_path / "odi.db"
    database.write_bytes(b"")
    monkeypatch.setenv("AGENTIC_ODI_DB", str(database))
    monkeypatch.setattr(doctor.os, "access", lambda path, mode: False)

    check = doctor.check_db_path()

    assert check.status == "fail"
    assert str(tmp_path) in check.summary


def test_integrity_passes_for_a_healthy_file(monkeypatch, tmp_path):
    database = tmp_path / "odi.db"
    connection = sqlite3.connect(database)
    connection.execute("CREATE TABLE t (id INTEGER)")
    connection.commit()
    connection.close()
    monkeypatch.setenv("AGENTIC_ODI_DB", str(database))

    assert doctor.check_db_integrity().status == "pass"


def test_a_healthy_studio_sidecar_passes(monkeypatch):
    monkeypatch.setattr(doctor, "_tcp", lambda host, port, timeout: (True, "connected"))
    monkeypatch.setattr(doctor, "_get", lambda url, timeout: (True, {"status": "ok"}))

    check, studio = doctor.check_studio_port(0.01)

    assert check.status == "pass"
    assert studio.reachable is True


def test_a_listener_that_is_not_the_studio_warns(monkeypatch):
    monkeypatch.setattr(doctor, "_tcp", lambda host, port, timeout: (True, "connected"))
    monkeypatch.setattr(doctor, "_get", lambda url, timeout: (True, {"status": "nope"}))

    check, studio = doctor.check_studio_port(0.01)

    assert check.status == "warn"
    assert studio.reachable is False
    assert check.remedy is not None


def test_studio_api_reads_the_mcp_url_it_reports(monkeypatch):
    studio = doctor.StudioState(reachable=True)
    monkeypatch.setattr(
        doctor,
        "_get",
        lambda url, timeout: (True, {"defaults": {"mcp_url": "http://localhost:8000/mcp"}}),
    )
    monkeypatch.setattr(doctor, "_tcp", lambda host, port, timeout: (True, "connected"))

    check = doctor.check_studio_api(studio, 0.01, offline=False)

    assert check.status == "pass"
    assert studio.config["mcp_url"] == "http://localhost:8000/mcp"


def test_studio_api_warns_when_the_mcp_endpoint_is_closed(monkeypatch):
    studio = doctor.StudioState(reachable=True)
    monkeypatch.setattr(
        doctor, "_get", lambda url, timeout: (True, {"mcp_url": "http://localhost:8000/mcp"})
    )
    monkeypatch.setattr(doctor, "_tcp", lambda host, port, timeout: (False, "refused"))

    check = doctor.check_studio_api(studio, 0.01, offline=False)

    assert check.status == "warn"
    assert check.remedy is not None


def test_studio_api_warns_when_the_configuration_is_missing(monkeypatch):
    studio = doctor.StudioState(reachable=True)
    monkeypatch.setattr(doctor, "_get", lambda url, timeout: (True, "not json"))

    check = doctor.check_studio_api(studio, 0.01, offline=False)

    assert check.status == "warn"
    assert check.remedy is not None


def test_mcp_endpoint_asks_the_studio_when_it_is_running(monkeypatch):
    studio = doctor.StudioState(reachable=True)
    monkeypatch.setattr(doctor, "_post", lambda url, body, timeout: (True, {"reachable": True}))
    assert doctor.check_mcp_endpoint(studio, 0.01, offline=False).status == "pass"

    monkeypatch.setattr(doctor, "_post", lambda url, body, timeout: (True, {"reachable": False}))
    check = doctor.check_mcp_endpoint(studio, 0.01, offline=False)
    assert check.status == "fail"
    assert check.remedy is not None


def test_mcp_endpoint_probes_the_default_url_when_the_studio_is_down(monkeypatch):
    studio = doctor.StudioState(reachable=False)
    monkeypatch.setattr(doctor, "_tcp", lambda host, port, timeout: (True, "connected"))
    assert doctor.check_mcp_endpoint(studio, 0.01, offline=False).status == "pass"

    monkeypatch.setattr(doctor, "_tcp", lambda host, port, timeout: (False, "refused"))
    assert doctor.check_mcp_endpoint(studio, 0.01, offline=False).status == "fail"

    monkeypatch.setattr(doctor, "DEFAULT_MCP_URL", "not-a-url")
    assert doctor.check_mcp_endpoint(studio, 0.01, offline=False).status == "skip"


def test_llm_endpoint_reports_a_healthy_and_an_unhealthy_model(monkeypatch):
    studio = doctor.StudioState(
        reachable=True, config={"base_url": "http://x", "api_key": "k", "model_name": "m"}
    )
    monkeypatch.setattr(
        doctor, "_post", lambda url, body, timeout: (True, {"healthy": True, "message": "gpt-4o"})
    )

    check = doctor.check_llm_endpoint(studio, 0.01, offline=False)
    assert (check.status, check.summary) == ("pass", "gpt-4o")

    monkeypatch.setattr(
        doctor,
        "_post",
        lambda url, body, timeout: (True, {"healthy": False, "message": "no model"}),
    )
    warned = doctor.check_llm_endpoint(studio, 0.01, offline=False)
    assert warned.status == "warn"
    assert warned.detail == "no model"
    assert warned.remedy is not None


def test_llm_endpoint_warns_when_the_probe_fails(monkeypatch):
    studio = doctor.StudioState(reachable=True)
    monkeypatch.setattr(doctor, "_post", lambda url, body, timeout: (False, "boom"))

    assert doctor.check_llm_endpoint(studio, 0.01, offline=False).status == "warn"


def test_connectors_config_passes_missing_and_readable_and_warns_on_broken_json(
    monkeypatch, tmp_path
):
    registry = tmp_path / "connectors.json"
    monkeypatch.setenv("AGENTIC_ODI_CONNECTORS_CONFIG", str(registry))
    assert doctor.check_connectors_config().status == "pass"

    registry.write_text("{}", encoding="utf-8")
    assert doctor.check_connectors_config().status == "pass"

    registry.write_text("{not json", encoding="utf-8")
    broken = doctor.check_connectors_config()
    assert broken.status == "warn"
    assert broken.remedy is not None


def test_paths_writable_names_the_directory_that_fails(monkeypatch, tmp_path):
    monkeypatch.setattr(doctor.paths, "install_root", lambda: tmp_path)
    monkeypatch.setattr(doctor.paths, "config_dir", lambda: tmp_path)
    monkeypatch.setattr(doctor.paths, "cache_dir", lambda: tmp_path)
    monkeypatch.setattr(doctor.os, "access", lambda path, mode: False)

    check = doctor.check_paths_writable()

    assert check.status == "fail"
    assert "install" in check.detail
    assert check.remedy is not None


class _Response:
    def __init__(self, payload, *, text="plain"):
        self._payload = payload
        self.text = text

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


def test_http_helpers_return_json_text_and_transport_errors(monkeypatch):
    monkeypatch.setattr(doctor.httpx, "get", lambda url, timeout: _Response({"ok": True}))
    monkeypatch.setattr(
        doctor.httpx, "post", lambda url, json, timeout: _Response(None, text="pong")
    )

    assert doctor._get("http://x", 0.01) == (True, {"ok": True})
    assert doctor._post("http://x", {}, 0.01) == (True, "pong")

    def refuse(*args, **kwargs):
        raise doctor.httpx.ConnectError("boom")

    monkeypatch.setattr(doctor.httpx, "get", refuse)
    monkeypatch.setattr(doctor.httpx, "post", refuse)
    assert doctor._get("http://x", 0.01)[0] is False
    assert doctor._post("http://x", {}, 0.01)[0] is False


def test_a_malformed_port_in_a_url_is_not_a_port():
    assert doctor._url_port("http://example.com:not-a-port/mcp") is None


def test_run_cli_refuses_a_non_positive_timeout():
    with pytest.raises(typer.Exit) as raised:
        doctor.run_cli(json_output=False, offline=True, timeout=0)

    assert raised.value.exit_code == 2
