"""The MCP server module must be inert to import (issue #461).

``build_repository()`` reads ``AGENTIC_ODI_DB``, creates the parent directory and
opens SQLite. None of that may happen as a side effect of importing the module or
of asking for ``--help``: each subprocess here points ``HOME`` and
``AGENTIC_ODI_DB`` at a fresh temporary directory and asserts the directory is
still empty afterwards. A subprocess, because a module another test already
imported would otherwise mask the result.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_IMPORT_MODULE = "import agentic_odi_mcp_server.mcp_server"


def _run(args: list[str], home: Path, db: Path | None) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["HOME"] = str(home)
    if db is None:
        env.pop("AGENTIC_ODI_DB", None)
    else:
        env["AGENTIC_ODI_DB"] = str(db)
    return subprocess.run(
        [sys.executable, *args],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _assert_nothing_built(
    result: subprocess.CompletedProcess[str], home: Path, db: Path | None
) -> None:
    assert result.returncode == 0, result.stderr
    assert not (home / ".agentic-odi").exists(), "import created the default home store"
    if db is not None:
        assert not db.exists(), f"import opened {db}"
        assert not db.parent.exists(), f"import created the store's parent directory {db.parent}"


def test_importing_the_server_opens_no_store(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    db = tmp_path / "data" / "odi.db"

    _assert_nothing_built(_run(["-c", _IMPORT_MODULE], home, db), home, db)


def test_importing_with_no_configuration_creates_no_home_directory(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()

    _assert_nothing_built(_run(["-c", _IMPORT_MODULE], home, None), home, None)


def test_help_touches_no_store(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    db = tmp_path / "data" / "odi.db"

    args = ["-m", "agentic_odi_mcp_server", "--help"]
    _assert_nothing_built(_run(args, home, db), home, db)
