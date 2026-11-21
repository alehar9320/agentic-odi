"""`odi data path` prints the resolved ODI and Studio database paths."""

from __future__ import annotations

import json

from agentic_odi_cli.cli import app
from typer.testing import CliRunner

runner = CliRunner()


def _invoke(args: list[str], monkeypatch) -> str:
    result = runner.invoke(app, ["--no-update", *args])
    assert result.exit_code == 0, result.output
    return result.output


def test_data_path_prints_default_paths(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("AGENTIC_ODI_DB", raising=False)
    monkeypatch.delenv("AGENTIC_ODI_STUDIO_DB", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))

    output = _invoke(["data", "path"], monkeypatch)

    assert f"{tmp_path}/.agentic-odi/odi.db" in output
    assert f"{tmp_path}/.agentic-odi/studio.db" in output


def test_data_path_honours_odi_env_override(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("AGENTIC_ODI_STUDIO_DB", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    odi = tmp_path / "custom" / "odi.db"
    monkeypatch.setenv("AGENTIC_ODI_DB", str(odi))

    output = _invoke(["data", "path"], monkeypatch)

    assert str(odi) in output
    assert f"{tmp_path}/.agentic-odi/studio.db" in output


def test_data_path_honours_studio_env_override(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("AGENTIC_ODI_DB", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    studio = tmp_path / "elsewhere" / "studio.db"
    monkeypatch.setenv("AGENTIC_ODI_STUDIO_DB", str(studio))

    output = _invoke(["data", "path"], monkeypatch)

    assert f"{tmp_path}/.agentic-odi/odi.db" in output
    assert str(studio) in output


def test_data_path_each_override_changes_only_its_own_path(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    odi = tmp_path / "odi-only.db"
    studio = tmp_path / "studio-only.db"
    monkeypatch.setenv("AGENTIC_ODI_DB", str(odi))
    monkeypatch.setenv("AGENTIC_ODI_STUDIO_DB", str(studio))

    output = _invoke(["data", "path"], monkeypatch)

    assert str(odi) in output
    assert str(studio) in output
    assert f"{tmp_path}/.agentic-odi/odi.db" not in output
    assert f"{tmp_path}/.agentic-odi/studio.db" not in output


def test_data_path_missing_parent_does_not_create_files(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("AGENTIC_ODI_DB", raising=False)
    monkeypatch.delenv("AGENTIC_ODI_STUDIO_DB", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))

    _invoke(["data", "path"], monkeypatch)

    assert not (tmp_path / ".agentic-odi").exists()


def test_data_path_json_emits_machine_readable_payload(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    odi = tmp_path / "odi.db"
    studio = tmp_path / "studio.db"
    monkeypatch.setenv("AGENTIC_ODI_DB", str(odi))
    monkeypatch.setenv("AGENTIC_ODI_STUDIO_DB", str(studio))

    output = _invoke(["data", "path", "--json"], monkeypatch)
    payload = json.loads(output)

    assert payload["odi_db"] == str(odi)
    assert payload["studio_db"] == str(studio)
    assert payload["odi_env"] == "AGENTIC_ODI_DB"
    assert payload["studio_env"] == "AGENTIC_ODI_STUDIO_DB"


def test_data_help_lists_path_and_existing_data_commands(monkeypatch) -> None:
    monkeypatch.setenv("HOME", "/tmp/odi-test-home")

    result = runner.invoke(app, ["--no-update", "data", "--help"])

    assert result.exit_code == 0, result.output
    assert "path" in result.output
    assert "Inspect the local ODI data files" in result.output


def test_store_reports_the_db_flag_path_over_the_env_override(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("AGENTIC_ODI_DB", str(tmp_path / "env.db"))
    explicit = tmp_path / "explicit.db"

    result = runner.invoke(app, ["--no-update", "--db", str(explicit), "store", "--json"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["db_path"] == str(explicit)


def test_store_reports_the_env_override_when_no_db_flag_is_given(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    odi = tmp_path / "env.db"
    monkeypatch.setenv("AGENTIC_ODI_DB", str(odi))

    result = runner.invoke(app, ["--no-update", "store", "--json"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["db_path"] == str(odi)
