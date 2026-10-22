"""The generated sources must never drift from the generator that made them.

The studio component and the CLI banner are generated code. If someone edits
them by hand, the mascot in the app icon and the mascot in the UI stop being
the same animal. These tests fail the build when that happens.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RENDER = ROOT / "brand" / "tools" / "render.py"

GENERATED_SOURCES = (
    "apps/studio/src/components/OdiMascot.tsx",
    "apps/cli/src/agentic_odi_cli/mascot.py",
)


def test_generated_sources_match_a_fresh_render() -> None:
    """``render.py --check`` must report no drift."""
    result = subprocess.run(
        [sys.executable, str(RENDER), "--check"],
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_generated_files_carry_a_do_not_edit_header() -> None:
    for rel in GENERATED_SOURCES:
        head = (ROOT / rel).read_text(encoding="utf-8")[:400]
        assert "GENERATED" in head, rel
        assert "do not edit" in head.lower(), rel


def test_generated_sources_exist() -> None:
    for rel in GENERATED_SOURCES:
        assert (ROOT / rel).is_file(), rel
