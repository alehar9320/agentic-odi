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


def test_clear_unsets_a_field(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    runner.invoke(app, ["profile", "set", "--product-name", "Acme App"])
    res = runner.invoke(app, ["profile", "set", "--clear", "product_name"])
    assert res.exit_code == 0
    from agentic_odi_cli.profile import load_baseline

    b = load_baseline()
    assert b is not None
    assert b.product_name is None


def test_clear_wins_over_set_in_the_same_call(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    res = runner.invoke(
        app,
        ["profile", "set", "--core-problem", "x", "--clear", "core_problem"],
    )
    assert res.exit_code == 0
    from agentic_odi_cli.profile import load_baseline

    b = load_baseline()
    assert b is not None
    assert b.core_problem is None


def test_an_unknown_clear_name_exits_2(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    res = runner.invoke(app, ["profile", "set", "--clear", "not_a_field"])
    assert res.exit_code == 2
    assert "product_name" in res.output
    assert "domain" in res.output
    assert "primary_user" in res.output
    assert "business_model" in res.output
    assert "core_problem" in res.output
    assert "current_focus" in res.output


def test_show_reports_a_malformed_profile_without_a_traceback(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from agentic_odi_cli.profile import baseline_file

    target = baseline_file()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text('{"a": 1,}')

    res = runner.invoke(app, ["profile", "show"])

    assert res.exit_code == 1
    assert "not valid JSON" in res.output
    assert "line" in res.output
    assert "Traceback" not in res.output


def test_show_distinguishes_none_from_empty(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    runner.invoke(app, ["profile", "set", "--product-name", ""])
    res = runner.invoke(app, ["profile", "show"])
    assert res.exit_code == 0
    assert "Product Name: (empty)" in res.output
    res = runner.invoke(app, ["profile", "set", "--clear", "product_name"])
    assert res.exit_code == 0
    res = runner.invoke(app, ["profile", "show"])
    assert "Product Name: —" in res.output
