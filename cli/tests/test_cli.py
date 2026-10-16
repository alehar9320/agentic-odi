import re

from typer.testing import CliRunner

from cli import version
from cli.cli import __version__, app

ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")


def _strip_ansi(text: str) -> str:
    return ANSI_ESCAPE.sub("", text)


def test_version_flag_prints_version():
    runner = CliRunner()
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert __version__ in _strip_ansi(result.output)


def test_help_flag_shows_usage():
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    output = _strip_ansi(result.output)
    assert "Usage" in output
    assert "--version" in output


def test_version_subcommand_matches_version_flag():
    runner = CliRunner()

    flag = runner.invoke(app, ["--version"])
    subcommand = runner.invoke(app, ["version"])

    assert flag.exit_code == 0
    assert subcommand.exit_code == 0
    assert _strip_ansi(subcommand.output) == _strip_ansi(flag.output)


def test_version_subcommand_prints_build_summary(monkeypatch):
    monkeypatch.setattr(version, "RELEASE_DATE_UTC", "2026-10-15T21:13:00Z")

    runner = CliRunner()
    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0
    assert "0.1.0 (2026-10-15)" in _strip_ansi(result.output)


def test_version_verbose_shows_build_details():
    runner = CliRunner()
    result = runner.invoke(app, ["--version", "--verbose"])

    assert result.exit_code == 0
    output = _strip_ansi(result.output)
    assert version.verbose_summary() in output
    assert version.build_summary() in output
    assert f"commit: {version.COMMIT}" in output
    assert f"target: {version.TARGET}" in output


def test_version_verbose_includes_release_date_when_set(monkeypatch):
    monkeypatch.setattr(version, "RELEASE_DATE_UTC", "2026-10-15T21:13:00Z")

    runner = CliRunner()
    result = runner.invoke(app, ["--version", "--verbose"])

    assert result.exit_code == 0
    assert "0.1.0 (2026-10-15)" in _strip_ansi(result.output)
