from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path

import pytest
from agentic_odi_orchestrator import (
    AgentTarget,
    OrchestratorSettings,
    default_target,
    load_settings,
    save_settings,
    settings_with_default_target,
)


def test_missing_config_is_an_empty_settings(tmp_path) -> None:
    settings = load_settings(tmp_path / "absent.json")
    assert settings.targets == []


def test_round_trip_writes_private_file(tmp_path) -> None:
    path = tmp_path / "openhands.json"
    settings = OrchestratorSettings(
        targets=[AgentTarget(alias="cloud", base_url="https://example.test")],
        default_target="cloud",
        poll_interval_s=5,
    )
    save_settings(settings, path)
    loaded = load_settings(path)
    assert loaded.default_target == "cloud"
    assert loaded.targets[0].alias == "cloud"
    if sys.platform != "win32":
        assert stat.S_IMODE(os.stat(path).st_mode) == 0o600


def test_invalid_json_is_reported_with_path(tmp_path) -> None:
    path = tmp_path / "openhands.json"
    path.write_text("{not json")
    with pytest.raises(ValueError, match="cannot read orchestrator config"):
        load_settings(path)


def test_non_object_config_is_rejected(tmp_path) -> None:
    path = tmp_path / "openhands.json"
    path.write_text(json.dumps([1, 2]))
    with pytest.raises(ValueError, match="must be a JSON object"):
        load_settings(path)


def test_env_overrides_paths(tmp_path, monkeypatch) -> None:
    from agentic_odi_orchestrator import config

    config_file = tmp_path / "custom.json"
    db_file = tmp_path / "custom.db"
    monkeypatch.setenv("AGENTIC_ODI_OPENHANDS_CONFIG", str(config_file))
    monkeypatch.setenv("AGENTIC_ODI_ORCHESTRATOR_DB", str(db_file))
    assert config.config_path() == config_file
    assert config.db_path() == db_file


def test_default_target_helper() -> None:
    target = default_target()
    assert target.alias == "cloud-main"
    settings = settings_with_default_target(OrchestratorSettings())
    assert settings.default_target == "cloud-main"
    # Existing targets are left alone.
    existing = OrchestratorSettings(
        targets=[AgentTarget(alias="mine", base_url="https://example.test")]
    )
    assert settings_with_default_target(existing) is existing


def test_default_paths_follow_xdg_and_home(tmp_path, monkeypatch) -> None:
    from agentic_odi_orchestrator import config

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.delenv("AGENTIC_ODI_OPENHANDS_CONFIG", raising=False)
    monkeypatch.delenv("AGENTIC_ODI_ORCHESTRATOR_DB", raising=False)

    assert config.config_dir() == tmp_path / "config" / "agentic-odi"
    assert config.config_path() == tmp_path / "config" / "agentic-odi" / "openhands.json"
    assert config.lock_path() == tmp_path / "config" / "agentic-odi" / "orchestrator.lock"
    assert config.db_path() == config.data_dir() / "orchestrator.db"


def test_heartbeat_and_workspace_follow_settings_overrides(tmp_path) -> None:
    from agentic_odi_orchestrator import config

    heartbeat = tmp_path / "heartbeat.json"
    settings = OrchestratorSettings(heartbeat_path=str(heartbeat), workspace_root=str(tmp_path))
    assert config.heartbeat_path(settings) == heartbeat
    assert config.workspace_root(settings) == tmp_path.resolve()

    defaults = OrchestratorSettings()
    assert config.heartbeat_path(defaults) == config.data_dir() / "orchestrator-heartbeat.json"
    assert config.workspace_root(defaults) == Path.cwd().resolve()
