"""``odi doctor`` — one read-only diagnosis of why the Studio will not start.

Checks run in order and independently. A check whose precondition failed becomes
``skip`` with a reason, never ``fail``. Doctor never creates the database, never
runs a migration, and never starts a server: a diagnosis that changes the
machine is not a diagnosis.

Exit codes: 0 when every check passes or warns, 1 when at least one fails, and
2 when the command itself cannot run (Typer owns usage errors).
"""

from __future__ import annotations

import importlib.metadata
import json
import os
import platform
import shutil
import socket
import sqlite3
import sys
import urllib.parse
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import typer

from agentic_odi_cli import paths, version

SCHEMA_VERSION = 1
STUDIO_HOST = "127.0.0.1"
STUDIO_PORT = 8100
DEFAULT_MCP_URL = "http://localhost:8000/mcp"
STUDIO_START_COMMAND = "uv run python -m agentic_odi_studio_api.main"
MCP_START_COMMAND = "uv run python -m agentic_odi_mcp_server"

STATUSES = ("pass", "warn", "fail", "skip")
_API_ENV_VAR = "AGENTIC_ODI_API_KEY"


@dataclass(frozen=True)
class Remedy:
    text: str
    command: str | None = None


@dataclass(frozen=True)
class Check:
    id: str
    status: str
    summary: str
    detail: str = ""
    remedy: Remedy | None = None

    def as_dict(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "id": self.id,
            "status": self.status,
            "summary": _redact(self.summary),
            "detail": _redact(self.detail),
        }
        if self.remedy is not None:
            body["remedy"] = {
                "text": _redact(self.remedy.text),
                "command": _redact(self.remedy.command or ""),
            }
        return body


@dataclass
class Report:
    checks: list[Check] = field(default_factory=list)
    environment: dict[str, Any] = field(default_factory=dict)

    @property
    def failed(self) -> bool:
        return any(check.status == "fail" for check in self.checks)

    @property
    def exit_code(self) -> int:
        return 1 if self.failed else 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "ok": not self.failed,
            "exit_code": self.exit_code,
            "environment": self.environment,
            "checks": [check.as_dict() for check in self.checks],
        }


def _redact(text: str) -> str:
    """Remove credentials: URL userinfo and the value of the API key."""
    if not text:
        return text
    cleaned = _redact_userinfo(text)
    secret = os.environ.get(_API_ENV_VAR)
    if secret:
        cleaned = cleaned.replace(secret, "***")
    return cleaned


def _redact_userinfo(text: str) -> str:
    parts = urllib.parse.urlsplit(text)
    if parts.scheme and parts.netloc and "@" in parts.netloc:
        netloc = parts.netloc.rsplit("@", 1)[1]
        return urllib.parse.urlunsplit(
            (parts.scheme, f"***@{netloc}", parts.path, parts.query, parts.fragment)
        )
    # Not a bare URL: redact userinfo anywhere inside a sentence.
    import re

    return re.sub(r"(https?://)[^/@\s]+@", r"\1***@", text)


def _env_names() -> list[str]:
    return sorted(name for name in os.environ if name.startswith("AGENTIC_ODI_"))


def _environment() -> dict[str, Any]:
    return {
        "platform": sys.platform,
        "python": sys.version.split()[0],
        "cli_version": version.VERSION,
        "commit": version.COMMIT,
        "target": version.TARGET,
        "env_vars": _env_names(),
    }


def _db_path() -> Path:
    raw = os.environ.get("AGENTIC_ODI_DB", "~/.agentic-odi/odi.db")
    return Path(raw).expanduser()


def _connectors_path() -> Path:
    override = os.environ.get("AGENTIC_ODI_CONNECTORS_CONFIG")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".config" / "agentic-odi" / "connectors.json"


def _cache_dir() -> Path:
    xdg = os.environ.get("XDG_CACHE_HOME")
    root = Path(xdg).expanduser() if xdg else Path.home() / ".cache"
    return root / "agentic-odi"


def find_repo_root(start: Path | None = None) -> Path | None:
    """Walk up for the two app packages, mirroring the desktop shell."""
    override = os.environ.get("AGENTIC_ODI_REPO_ROOT")
    if override:
        candidate = Path(override).expanduser()
        return candidate if candidate.is_dir() else None

    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / "apps" / "mcp-server").is_dir() and (
            candidate / "apps" / "studio-api"
        ).is_dir():
            return candidate
    return None


def _tcp(host: str, port: int, timeout: float) -> tuple[bool, str]:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, f"connected to {host}:{port}"
    except OSError as exc:
        return False, f"{type(exc).__name__}: {exc}"


def _get(url: str, timeout: float) -> tuple[bool, Any]:
    try:
        response = httpx.get(url, timeout=timeout)
    except httpx.HTTPError as exc:
        return False, f"{type(exc).__name__}: {exc}"
    try:
        return True, response.json()
    except ValueError:
        return True, response.text


def _post(url: str, body: dict[str, Any], timeout: float) -> tuple[bool, Any]:
    try:
        response = httpx.post(url, json=body, timeout=timeout)
    except httpx.HTTPError as exc:
        return False, f"{type(exc).__name__}: {exc}"
    try:
        return True, response.json()
    except ValueError:
        return True, response.text


def _url_port(url: str) -> int | None:
    parts = urllib.parse.urlsplit(url)
    try:
        return parts.port or (443 if parts.scheme == "https" else 80)
    except ValueError:
        return None


def _url_host(url: str) -> str | None:
    return urllib.parse.urlsplit(url).hostname


@dataclass
class StudioState:
    reachable: bool
    config: dict[str, Any] = field(default_factory=dict)


def check_cli_version() -> Check:
    if version.COMMIT == "dev":
        return Check(
            "cli.version",
            "warn",
            f"Development build {version.VERSION}",
            "commit is 'dev'; a release build reports its commit.",
            Remedy(
                "Install a release build",
                "curl -fsSL https://github.com/alehar9320/agentic-odi/releases/latest/download/install.sh | sh",
            ),
        )
    return Check(
        "cli.version",
        "pass",
        f"{version.VERSION} ({version.COMMIT}, {version.TARGET})",
    )


def check_versions_parity() -> Check:
    wanted = ("agentic-odi-cli", "agentic-odi-mcp-server", "agentic-odi-studio-api")
    found: dict[str, str] = {}
    for name in wanted:
        try:
            found[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            continue
    if len(found) != len(wanted):
        return Check(
            "versions.parity",
            "skip",
            "Package metadata is unavailable",
            f"found {', '.join(sorted(found)) or 'none'}",
            Remedy("Run from a uv install", "uv sync --all-packages"),
        )
    unique = set(found.values())
    if len(unique) == 1:
        return Check("versions.parity", "pass", f"CLI, MCP server and sidecar all {unique.pop()}")
    detail = "; ".join(f"{name} {value}" for name, value in sorted(found.items()))
    return Check(
        "versions.parity",
        "fail",
        "CLI, MCP server and sidecar versions disagree",
        detail,
        Remedy("Reinstall the workspace so every package matches", "uv sync --all-packages"),
    )


def check_python_version() -> Check:
    major, minor = (int(part) for part in platform.python_version_tuple()[:2])
    if (major, minor) >= (3, 10):
        return Check("python.version", "pass", sys.version.split()[0])
    return Check(
        "python.version",
        "fail",
        "Python 3.10 or newer is required",
        sys.version.split()[0],
        Remedy("Install Python 3.10+ and reinstall the CLI"),
    )


def check_uv() -> Check:
    if paths.is_frozen():
        return Check("uv.present", "skip", "Frozen build; uv is not required")
    found = shutil.which("uv")
    if found:
        return Check("uv.present", "pass", found)
    return Check(
        "uv.present",
        "fail",
        "uv is not on PATH",
        "the Studio is started with `uv run`",
        Remedy("Install uv", "curl -LsSf https://astral.sh/uv/install.sh | sh"),
    )


def check_workspace_root() -> Check:
    root = find_repo_root()
    if root is not None:
        return Check("workspace.root", "pass", str(root))
    return Check(
        "workspace.root",
        "warn",
        "No workspace root found",
        "checked AGENTIC_ODI_REPO_ROOT and the current directory's parents",
        Remedy(
            "Run from the repository, or set AGENTIC_ODI_REPO_ROOT",
            "AGENTIC_ODI_REPO_ROOT=$(pwd) odi doctor",
        ),
    )


def check_spa_build() -> Check:
    root = find_repo_root()
    if root is None:
        return Check("spa.build", "skip", "No workspace root to look in")
    index = root / "apps" / "studio" / "dist" / "index.html"
    if index.is_file():
        return Check("spa.build", "pass", str(index))
    return Check(
        "spa.build",
        "warn",
        "The Studio has not been built",
        f"missing {index}",
        Remedy("Build the Studio once", "npm --prefix apps/studio run build"),
    )


def check_db_path() -> Check:
    path = _db_path()
    if str(path) == ":memory:":
        return Check("db.path", "skip", "In-memory database")
    parent = path.parent
    if path.is_file():
        if os.access(parent, os.W_OK):
            return Check("db.path", "pass", str(path))
        return Check(
            "db.path",
            "fail",
            f"The database directory is not writable: {parent}",
            str(path),
            Remedy(
                "Fix the directory permissions or set AGENTIC_ODI_DB",
                "AGENTIC_ODI_DB=$HOME/.agentic-odi/odi.db odi doctor",
            ),
        )
    if parent.is_dir() and not os.access(parent, os.W_OK):
        return Check(
            "db.path",
            "fail",
            f"The database directory is not writable: {parent}",
            str(path),
            Remedy(
                "Fix the directory permissions or set AGENTIC_ODI_DB",
                "AGENTIC_ODI_DB=$HOME/.agentic-odi/odi.db odi doctor",
            ),
        )
    return Check(
        "db.path",
        "warn",
        "No database yet",
        f"{path} is created on the first write",
    )


def check_db_integrity() -> Check:
    path = _db_path()
    if str(path) == ":memory:" or not path.is_file():
        return Check("db.integrity", "skip", "No database file to check")
    uri = f"file:{path}?mode=ro"
    try:
        connection = sqlite3.connect(uri, uri=True)
        try:
            result = connection.execute("PRAGMA quick_check").fetchone()
        finally:
            connection.close()
    except sqlite3.Error as exc:
        return Check(
            "db.integrity",
            "fail",
            "The database could not be read",
            str(exc),
            Remedy("Back up the database and restore it from a known-good copy"),
        )
    status = str(result[0]) if result else "no result"
    if status == "ok":
        return Check("db.integrity", "pass", "PRAGMA quick_check: ok")
    return Check(
        "db.integrity",
        "fail",
        f"PRAGMA quick_check reported {status}",
        str(path),
        Remedy("Back up the database and restore it from a known-good copy"),
    )


def check_studio_port(timeout: float) -> tuple[Check, StudioState]:
    listening, detail = _tcp(STUDIO_HOST, STUDIO_PORT, timeout)
    if not listening:
        return (
            Check(
                "port.studio",
                "fail",
                f"Nothing is listening on {STUDIO_HOST}:{STUDIO_PORT}",
                detail,
                Remedy("Start the Studio sidecar", STUDIO_START_COMMAND),
            ),
            StudioState(reachable=False),
        )
    ok, payload = _get(f"http://{STUDIO_HOST}:{STUDIO_PORT}/health", timeout)
    if ok and isinstance(payload, dict) and payload.get("status") == "ok":
        return (
            Check("port.studio", "pass", f"Studio sidecar healthy on port {STUDIO_PORT}"),
            StudioState(reachable=True),
        )
    return (
        Check(
            "port.studio",
            "warn",
            f"A listener on {STUDIO_HOST}:{STUDIO_PORT} is not the Studio sidecar",
            str(payload),
            Remedy("Stop the other process or start the sidecar on 8100", STUDIO_START_COMMAND),
        ),
        StudioState(reachable=False),
    )


def check_studio_api(studio: StudioState, timeout: float, offline: bool) -> Check:
    if offline:
        return Check("studio.api", "skip", "--offline")
    if not studio.reachable:
        return Check("studio.api", "skip", "The Studio sidecar is not running")
    ok, payload = _get(f"http://{STUDIO_HOST}:{STUDIO_PORT}/api/config", timeout)
    if not ok or not isinstance(payload, dict):
        return Check(
            "studio.api",
            "warn",
            "The Studio API did not return configuration",
            str(payload),
            Remedy("Restart the Studio sidecar", STUDIO_START_COMMAND),
        )
    raw_defaults = payload.get("defaults")
    defaults: dict[str, Any] = raw_defaults if isinstance(raw_defaults, dict) else {}
    studio.config = {**payload, **defaults}
    mcp_url = str(studio.config.get("mcp_url") or DEFAULT_MCP_URL)
    port = _url_port(mcp_url)
    host = _url_host(mcp_url)
    if host and port:
        reachable, detail = _tcp(host, port, timeout)
        if not reachable:
            return Check(
                "studio.api",
                "warn",
                "The Studio is running, but its MCP endpoint is closed",
                f"{host}:{port} — {detail}",
                Remedy("Start the MCP server", MCP_START_COMMAND),
            )
    return Check("studio.api", "pass", f"Studio API answered on port {STUDIO_PORT}")


def check_mcp_endpoint(studio: StudioState, timeout: float, offline: bool) -> Check:
    if offline:
        return Check("mcp.endpoint", "skip", "--offline")
    if studio.reachable:
        mcp_url = str(studio.config.get("mcp_url") or DEFAULT_MCP_URL)
        ok, payload = _post(
            f"http://{STUDIO_HOST}:{STUDIO_PORT}/api/health/mcp",
            {"mcp_url": mcp_url},
            timeout,
        )
        if ok and isinstance(payload, dict) and payload.get("reachable"):
            return Check("mcp.endpoint", "pass", f"MCP server reachable at {mcp_url}")
        return Check(
            "mcp.endpoint",
            "fail",
            f"The MCP server is not reachable at {mcp_url}",
            str(payload),
            Remedy("Start the MCP server", MCP_START_COMMAND),
        )

    mcp_url = DEFAULT_MCP_URL
    host = _url_host(mcp_url)
    port = _url_port(mcp_url)
    if not host or not port:
        return Check("mcp.endpoint", "skip", f"Could not parse {mcp_url}")
    reachable, detail = _tcp(host, port, timeout)
    if reachable:
        return Check("mcp.endpoint", "pass", f"{host}:{port} is accepting connections")
    return Check(
        "mcp.endpoint",
        "fail",
        f"The MCP server is not reachable at {mcp_url}",
        detail,
        Remedy("Start the MCP server", MCP_START_COMMAND),
    )


def check_llm_endpoint(studio: StudioState, timeout: float, offline: bool) -> Check:
    if offline:
        return Check("llm.endpoint", "skip", "--offline")
    if not studio.reachable:
        return Check("llm.endpoint", "skip", "The Studio sidecar is not running")
    body = {
        "base_url": studio.config.get("base_url", ""),
        "api_key": studio.config.get("api_key", ""),
        "model": studio.config.get("model_name", ""),
    }
    ok, payload = _post(f"http://{STUDIO_HOST}:{STUDIO_PORT}/api/health/llm", body, timeout)
    if not ok or not isinstance(payload, dict):
        return Check("llm.endpoint", "warn", "The model health probe failed", str(payload))
    if payload.get("healthy"):
        return Check("llm.endpoint", "pass", str(payload.get("message") or "model reachable"))
    return Check(
        "llm.endpoint",
        "warn",
        "No model is reachable; by-hand editing still works",
        str(payload.get("message") or ""),
        Remedy("Start a local model or configure one in Settings"),
    )


def check_connectors_config() -> Check:
    path = _connectors_path()
    if not path.is_file():
        return Check("connectors.config", "pass", "No connectors configured yet")
    try:
        json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return Check(
            "connectors.config",
            "warn",
            "connectors.json could not be read",
            str(exc),
            Remedy("Fix or remove the file", f"{path}"),
        )
    return Check("connectors.config", "pass", str(path))


def check_paths_writable() -> Check:
    targets = {
        "install": paths.install_root(),
        "config": paths.config_dir(),
        "cache": _cache_dir(),
    }
    broken: list[str] = []
    for name, path in targets.items():
        probe = path if path.exists() else path.parent
        if probe.exists() and not os.access(probe, os.W_OK):
            broken.append(f"{name} ({path})")
    if broken:
        return Check(
            "paths.writable",
            "fail",
            "Some directories are not writable",
            ", ".join(broken),
            Remedy("Fix the directory permissions", "chmod u+w ~/.config/agentic-odi"),
        )
    return Check(
        "paths.writable",
        "pass",
        ", ".join(f"{name}={path}" for name, path in targets.items()),
    )


def run_doctor(offline: bool = False, timeout: float = 2.0) -> Report:
    """Run every check, read-only, in a stable order."""
    report = Report(environment=_environment())
    report.checks.append(check_cli_version())
    report.checks.append(check_versions_parity())
    report.checks.append(check_python_version())
    report.checks.append(check_uv())
    report.checks.append(check_workspace_root())
    report.checks.append(check_spa_build())
    report.checks.append(check_db_path())
    report.checks.append(check_db_integrity())

    port_check, studio = check_studio_port(timeout)
    report.checks.append(port_check)
    report.checks.append(check_studio_api(studio, timeout, offline))
    report.checks.append(check_mcp_endpoint(studio, timeout, offline))
    report.checks.append(check_llm_endpoint(studio, timeout, offline))
    report.checks.append(check_connectors_config())
    report.checks.append(check_paths_writable())
    return report


def render_human(report: Report) -> str:
    lines = [
        "Agentic ODI doctor",
        f"db: {_redact(str(_db_path()))}",
        f"install: {_redact(str(paths.install_root()))}",
        f"config: {_redact(str(paths.config_dir()))}",
        "",
    ]
    for check in report.checks:
        line = f"{check.status.upper():4} {check.id} — {_redact(check.summary)}"
        if check.detail:
            line = f"{line} ({_redact(check.detail)})"
        lines.append(line)

    remedies = [check.remedy for check in report.checks if check.status == "fail" and check.remedy]
    if remedies:
        lines.append("")
        lines.append("What to try:")
        for remedy in remedies:
            line = f"  - {_redact(remedy.text)}"
            if remedy.command:
                line = f"{line}: {_redact(remedy.command)}"
            lines.append(line)
    return "\n".join(lines)


def run_cli(json_output: bool, offline: bool, timeout: float) -> None:
    if timeout <= 0:
        typer.echo("--timeout must be greater than zero", err=True)
        raise typer.Exit(code=2)

    report = run_doctor(offline=offline, timeout=timeout)
    if json_output:
        typer.echo(json.dumps(report.as_dict(), indent=2))
    else:
        typer.echo(render_human(report))
    raise typer.Exit(code=report.exit_code)


__all__ = [
    "Check",
    "Remedy",
    "Report",
    "find_repo_root",
    "render_human",
    "run_cli",
    "run_doctor",
]


# Keep the callable table easy to find for anyone extending doctor.
CHECKS: tuple[Callable[..., Check], ...] = (
    check_cli_version,
    check_versions_parity,
    check_python_version,
    check_uv,
    check_workspace_root,
    check_spa_build,
    check_db_path,
    check_db_integrity,
)
