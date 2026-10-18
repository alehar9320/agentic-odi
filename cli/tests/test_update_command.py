# cli/tests/test_update_command.py
from unittest.mock import ANY, patch

from typer.testing import CliRunner

import cli.cli as cli_module
from cli.cli import app
from cli.update import UpdateError
from cli.version import __version__


def test_update_check_up_to_date():
    runner = CliRunner()
    with patch("cli.update.latest_release", return_value=None):
        result = runner.invoke(app, ["update", "--check"])
    assert result.exit_code == 0
    assert "up to date" in result.output.lower()


def test_update_check_available():
    runner = CliRunner()
    with patch("cli.update.latest_release", return_value="0.2.0"):
        result = runner.invoke(app, ["update", "--check"])
    assert result.exit_code == 0
    assert "0.2.0" in result.output


def test_update_source_install_message():
    runner = CliRunner()
    with patch("cli.paths.is_frozen", return_value=False):
        result = runner.invoke(app, ["update"])
    assert result.exit_code == 0
    assert "source" in result.output.lower() or "not a bundled" in result.output.lower()


def test_no_update_flag_suppresses_startup_check(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTIC_ODI_DB", str(tmp_path / "odi.db"))
    runner = CliRunner()
    with patch("cli.update.maybe_auto_update") as mock_update:
        runner.invoke(app, ["--no-update", "outcomes", "score", "8", "2"])
    mock_update.assert_not_called()


def test_update_explicit_version_installs(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTIC_ODI_INSTALL_DIR", str(tmp_path))
    archive = tmp_path / "archive.tar.gz"
    archive.write_bytes(b"payload")
    runner = CliRunner()
    with (
        patch("cli.paths.is_frozen", return_value=True),
        patch("cli.update.download", return_value=archive) as mock_download,
        patch("cli.update.perform_update") as mock_perform,
        patch("cli.update.latest_release") as mock_latest,
    ):
        result = runner.invoke(app, ["--no-update", "update", "--version", "0.3.0"])
    assert result.exit_code == 0
    assert "Updated to v0.3.0" in result.output
    mock_download.assert_called_once()
    mock_perform.assert_called_once()
    mock_latest.assert_not_called()


def test_update_already_up_to_date(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTIC_ODI_INSTALL_DIR", str(tmp_path))
    runner = CliRunner()
    with (
        patch("cli.paths.is_frozen", return_value=True),
        patch("cli.update.latest_release", return_value=None),
        patch("cli.update.download") as mock_download,
    ):
        result = runner.invoke(app, ["--no-update", "update"])
    assert result.exit_code == 0
    assert "up to date" in result.output.lower()
    mock_download.assert_not_called()


def test_update_force_reinstalls_current_version(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTIC_ODI_INSTALL_DIR", str(tmp_path))
    archive = tmp_path / "archive.tar.gz"
    archive.write_bytes(b"payload")
    runner = CliRunner()
    with (
        patch("cli.paths.is_frozen", return_value=True),
        patch("cli.update.latest_release", return_value=None),
        patch("cli.update.download", return_value=archive) as mock_download,
        patch("cli.update.perform_update") as mock_perform,
    ):
        result = runner.invoke(app, ["--no-update", "update", "--force"])
    assert result.exit_code == 0
    assert f"Updated to v{__version__}" in result.output
    mock_download.assert_called_once_with(__version__, ANY)
    mock_perform.assert_called_once()


def test_update_now_without_symlink_defers_reexec(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTIC_ODI_INSTALL_DIR", str(tmp_path))
    archive = tmp_path / "archive.tar.gz"
    archive.write_bytes(b"payload")
    runner = CliRunner()
    with (
        patch("cli.paths.is_frozen", return_value=True),
        patch("cli.update.latest_release", return_value="0.2.0"),
        patch("cli.update.download", return_value=archive),
        patch("cli.update.perform_update"),
        patch("cli.cli.os.execv") as mock_exec,
    ):
        result = runner.invoke(app, ["--no-update", "update", "--now"])
    assert result.exit_code == 0
    assert "Updated to v0.2.0" in result.output
    assert "take effect on the next run" in result.output
    mock_exec.assert_not_called()


def test_update_failure_exits_nonzero(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTIC_ODI_INSTALL_DIR", str(tmp_path))
    runner = CliRunner()
    with (
        patch("cli.paths.is_frozen", return_value=True),
        patch("cli.update.latest_release", return_value="0.2.0"),
        patch("cli.update.download", side_effect=UpdateError("network down")),
    ):
        result = runner.invoke(app, ["--no-update", "update"])
    assert result.exit_code == 1
    assert "Update failed" in result.output


def test_startup_auto_update_prints_notice(capsys):
    with patch("cli.update.maybe_auto_update", return_value="0.2.0"):
        cli_module._startup_auto_update(False)
    assert "Updated to v0.2.0 — takes effect next run" in capsys.readouterr().out


def test_startup_auto_update_swallows_exceptions():
    with patch("cli.update.maybe_auto_update", side_effect=RuntimeError("boom")):
        cli_module._startup_auto_update(False)


def test_root_callback_spawns_daemon_startup_thread():
    runner = CliRunner()
    with patch("cli.cli.threading.Thread") as mock_thread:
        result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    mock_thread.assert_called_once()
    assert mock_thread.call_args.kwargs["daemon"] is True


def test_root_callback_skips_thread_with_no_update_flag():
    runner = CliRunner()
    with patch("cli.cli.threading.Thread") as mock_thread:
        result = runner.invoke(app, ["--no-update", "version"])
    assert result.exit_code == 0
    mock_thread.assert_not_called()
