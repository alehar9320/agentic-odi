"""Importing the MCP server must not build a store or touch the filesystem.

This is the regression proof for the composition root: the module used to run
``build_repository()`` at import, which read ``AGENTIC_ODI_DB``, created
``~/.agentic-odi``, opened the database, and replayed the event log before
``main()`` ran. A fresh process now imports with no side effect, and a tool
works once ``configure()`` names a store.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_IMPORT_SCRIPT = """
import os
import sqlite3
import sys


def _explode(*args, **kwargs):
    raise AssertionError("import must not touch the filesystem or the store")


os.makedirs = _explode
sqlite3.connect = _explode

import agentic_odi_mcp_server.mcp_server  # noqa: E402

home = os.environ["HOME"]
assert not os.path.exists(os.path.join(home, ".agentic-odi")), "import created the data dir"

from agentic_odi_core import InMemoryRepository  # noqa: E402
from agentic_odi_mcp_server import configure  # noqa: E402

configure(InMemoryRepository())
print("import-clean")
"""


def test_import_has_no_side_effects(tmp_path: Path) -> None:
    env = {**os.environ, "HOME": str(tmp_path)}
    env.pop("AGENTIC_ODI_DB", None)

    result = subprocess.run(
        [sys.executable, "-c", _IMPORT_SCRIPT],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )

    assert result.returncode == 0, result.stderr
    assert "import-clean" in result.stdout
    assert not (tmp_path / ".agentic-odi").exists()
