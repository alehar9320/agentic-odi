"""Top-level CLI behavior: version, help, and backend selection."""

from __future__ import annotations

import re

from typer.testing import CliRunner

from cli.cli import app
from cli.version import __version__

ANSI = re.compile(r"\x1b\[[0-9;]*m")
runner = CliRunner()


def _strip(text: str) -> str:
    return ANSI.sub("", text)


def test_version_flag_prints_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in _strip(result.output)


def test_version_command_prints_version():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in _strip(result.output)


def test_help_flag_shows_usage():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    output = _strip(result.output)
    assert "Usage" in output
    assert "--version" in output
    assert "--backend" in output


def test_no_args_shows_help():
    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "Usage" in _strip(result.output)


def test_unknown_backend_reports_error_with_exit_1():
    result = runner.invoke(app, ["--backend", "warp", "score", "8", "2"])
    assert result.exit_code == 1
    assert "unknown backend: warp" in _strip(result.output)
