from typer.testing import CliRunner

from cli.cli import __version__, app


def test_version_flag_prints_version():
    runner = CliRunner()
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert __version__ in result.output


def test_help_flag_shows_usage():
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "Usage" in result.output
    assert "--version" in result.output
