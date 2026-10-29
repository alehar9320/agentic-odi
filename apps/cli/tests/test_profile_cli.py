"""Tests for profile management and setup wizard CLI commands."""

from __future__ import annotations

import json

from agentic_odi_cli.cli import app
from typer.testing import CliRunner

runner = CliRunner()


def test_profile_path(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    res = runner.invoke(app, ["profile", "path"])
    assert res.exit_code == 0
    assert "agentic-odi" in res.output


def test_profile_set_and_show(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

    res_set = runner.invoke(
        app,
        [
            "profile",
            "set",
            "--product-name",
            "Acme App",
            "--primary-user",
            "Developers",
        ],
    )
    assert res_set.exit_code == 0

    res_show = runner.invoke(app, ["profile", "show"])
    assert res_show.exit_code == 0
    assert "Acme App" in res_show.output
    assert "Developers" in res_show.output

    res_json = runner.invoke(app, ["profile", "show", "--json"])
    assert res_json.exit_code == 0
    data = json.loads(res_json.output)
    assert data["product_name"] == "Acme App"
    assert data["primary_user"] == "Developers"


def test_setup_wizard(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    user_input = "Acme Tool\nacme.com\nDevs\nSaaS\nErrors\nSetup\n"
    res = runner.invoke(app, ["setup"], input=user_input)
    assert res.exit_code == 0
    assert "Baseline configured successfully" in res.output

    res_show = runner.invoke(app, ["profile", "show", "--json"])
    data = json.loads(res_show.output)
    assert data["product_name"] == "Acme Tool"
    assert data["domain"] == "acme.com"
