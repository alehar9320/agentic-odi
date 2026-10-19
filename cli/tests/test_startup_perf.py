"""Guard against importing heavy dependencies at CLI module load time.

``agentic-odi --version`` and ``--help`` must not pull in the MCP client,
the connectors package, or the core domain layer just to run.
"""

from __future__ import annotations

import subprocess
import sys

_HEAVY_MODULES = ("fastmcp", "connectors", "core")


def test_importing_cli_entrypoint_does_not_load_heavy_modules():
    code = (
        "import sys; import cli.cli; "
        "print(','.join(m for m in "
        f"{list(_HEAVY_MODULES)!r} if m in sys.modules))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
    )
    loaded = [name for name in result.stdout.strip().split(",") if name]
    assert loaded == [], f"heavy modules imported at load time: {loaded}"
