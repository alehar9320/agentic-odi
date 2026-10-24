import json
import re

from agentic_odi_cli import version
from agentic_odi_cli.cli import __version__, app
from typer.testing import CliRunner

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


def test_help_lists_global_backend_options():
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    output = _strip_ansi(result.output)
    assert "--backend" in output
    assert "--db" in output
    assert "--mcp-url" in output
    assert "customer-outcomes" in output
    assert "score" in output


def test_no_args_prints_help_when_not_a_tty():
    runner = CliRunner()
    result = runner.invoke(app, [])

    assert result.exit_code == 0
    assert "Usage" in _strip_ansi(result.output)


def test_unknown_backend_exits_nonzero():
    runner = CliRunner()
    result = runner.invoke(app, ["--backend", "warp", "score", "8", "2"])

    assert result.exit_code == 1
    assert "unknown backend: warp" in _strip_ansi(result.output)


def test_score_command_computes_opportunity():
    runner = CliRunner()
    result = runner.invoke(app, ["score", "8", "2"])

    assert result.exit_code == 0, result.output
    assert "14.00" in _strip_ansi(result.output)


def test_score_command_out_of_range_errors():
    runner = CliRunner()
    result = runner.invoke(app, ["score", "11", "2"])

    assert result.exit_code != 0


def test_schema_command_emits_json_entities():
    runner = CliRunner()
    result = runner.invoke(app, ["schema"])

    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert "Job" in data
    assert "Step" in data
    assert "Outcome" in data


def test_framework_guidelines_command_prints_text():
    runner = CliRunner()
    result = runner.invoke(app, ["framework-guidelines"])

    assert result.exit_code == 0, result.output
    assert "Outcome-Driven Innovation" in _strip_ansi(result.output)


def test_capabilities_command_prints_text():
    runner = CliRunner()
    result = runner.invoke(app, ["capabilities"])

    assert result.exit_code == 0, result.output
    assert "Manage Jobs-to-be-Done" in _strip_ansi(result.output)
