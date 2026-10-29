import re

from agentic_odi_cli import version
from agentic_odi_cli.cli import __version__, app
from typer.testing import CliRunner

ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")


def _strip_ansi(text: str) -> str:
    return ANSI_ESCAPE.sub("", text)


def test_version_subcommand_prints_build_summary_by_default():
    runner = CliRunner()
    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0
    assert version.build_summary() in _strip_ansi(result.output)


def test_version_subcommand_verbose_prints_version_and_build_metadata():
    runner = CliRunner()
    result = runner.invoke(app, ["version", "--verbose"])

    assert result.exit_code == 0
    output = _strip_ansi(result.output)
    assert __version__ in output
    assert f"commit: {version.COMMIT}" in output
    assert f"target: {version.TARGET}" in output
