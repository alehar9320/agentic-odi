import re

from typer.testing import CliRunner

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
