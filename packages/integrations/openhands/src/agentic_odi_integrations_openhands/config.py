"""Configuration, database, lock, and heartbeat paths.

Configuration is a small JSON file the user owns; the daemon never writes it.
The flow's only secret is the OpenHands API key, which is normally read from
an environment variable and only stored literally when the user insists.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from agentic_odi_integrations_openhands.models import AgentTarget, OrchestratorSettings

CONFIG_FILE_NAME = "openhands.json"
DB_FILE_NAME = "orchestrator.db"
LOCK_FILE_NAME = "orchestrator.lock"
HEARTBEAT_FILE_NAME = "orchestrator-heartbeat.json"


def config_dir() -> Path:
    if sys.platform == "win32":
        app_data = os.environ.get("APPDATA")
        base = Path(app_data) if app_data else Path.home() / "AppData" / "Roaming"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "agentic-odi"


def data_dir() -> Path:
    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA")
        base = Path(local) if local else Path.home() / "AppData" / "Local"
        return base / "agentic-odi"
    return Path.home() / ".agentic-odi"


def config_path() -> Path:
    override = os.environ.get("AGENTIC_ODI_OPENHANDS_CONFIG")
    return Path(override).expanduser() if override else config_dir() / CONFIG_FILE_NAME


def db_path() -> Path:
    override = os.environ.get("AGENTIC_ODI_ORCHESTRATOR_DB")
    return Path(override).expanduser() if override else data_dir() / DB_FILE_NAME


def lock_path() -> Path:
    return config_dir() / LOCK_FILE_NAME


def heartbeat_path(settings: OrchestratorSettings) -> Path:
    if settings.heartbeat_path:
        return Path(settings.heartbeat_path).expanduser()
    return data_dir() / HEARTBEAT_FILE_NAME


def workspace_root(settings: OrchestratorSettings) -> Path:
    if settings.workspace_root:
        return Path(settings.workspace_root).expanduser().resolve()
    return Path.cwd().resolve()


def _ensure_private_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path, 0o700)
    except OSError:  # pragma: no cover - best effort on exotic filesystems
        pass


def load_settings(path: Path | None = None) -> OrchestratorSettings:
    target = path or config_path()
    if not target.exists():
        return OrchestratorSettings()
    try:
        payload = json.loads(target.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read orchestrator config at {target}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"orchestrator config at {target} must be a JSON object")
    return OrchestratorSettings.model_validate(payload)


def save_settings(settings: OrchestratorSettings, path: Path | None = None) -> Path:
    target = path or config_path()
    _ensure_private_dir(target.parent)
    payload = settings.model_dump(mode="json")
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2))
    os.replace(tmp, target)
    try:
        os.chmod(target, 0o600)
    except OSError:  # pragma: no cover
        pass
    return target


def default_target() -> AgentTarget:
    from agentic_odi_openhands.client import DEFAULT_BASE_URL

    return AgentTarget(alias="cloud-main", base_url=DEFAULT_BASE_URL)


def settings_with_default_target(settings: OrchestratorSettings) -> OrchestratorSettings:
    """A convenience for first-run setup; never called by the daemon."""
    if not settings.targets:
        settings = settings.model_copy(
            update={"targets": [default_target()], "default_target": "cloud-main"}
        )
    return settings
