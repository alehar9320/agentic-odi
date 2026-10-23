"""Tests for settings and feature flags CLI commands."""

from __future__ import annotations

import json

from agentic_odi_cli.cli import app
from typer.testing import CliRunner

runner = CliRunner()


def test_flags_list_human_and_json(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

    res_list = runner.invoke(app, ["settings", "flags", "list"])
    assert res_list.exit_code == 0
    assert "experimental_connectors" in res_list.output
    assert "auto_update" in res_list.output

    res_json = runner.invoke(app, ["settings", "flags", "list", "--json"])
    assert res_json.exit_code == 0
    items = json.loads(res_json.output)
    keys = {item["key"] for item in items}
    assert "developer_mode" in keys
    assert "advanced_metrics" in keys


def test_flags_get_set_reset_flow(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

    # Get initial state
    res_get = runner.invoke(app, ["settings", "flags", "get", "developer_mode"])
    assert res_get.exit_code == 0
    assert "DISABLED" in res_get.output

    # Set flag
    res_set = runner.invoke(app, ["settings", "flags", "set", "developer_mode", "on"])
    assert res_set.exit_code == 0
    assert "enabled" in res_set.output

    # Get updated state
    res_get_updated = runner.invoke(app, ["settings", "flags", "get", "developer_mode", "--json"])
    assert res_get_updated.exit_code == 0
    data = json.loads(res_get_updated.output)
    assert data["enabled"] is True

    # Reset flag
    res_reset = runner.invoke(app, ["settings", "flags", "reset", "developer_mode"])
    assert res_reset.exit_code == 0

    res_get_reset = runner.invoke(app, ["settings", "flags", "get", "developer_mode", "--json"])
    assert res_get_reset.exit_code == 0
    data_reset = json.loads(res_get_reset.output)
    assert data_reset["enabled"] is False
