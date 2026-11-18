"""No library code in the connectors package prints to stdout or stderr.

The package is imported by the CLI, the sidecar, and the MCP server, each of
which configures logging differently. A bare ``print`` bypasses the level, the
handler, and the redaction the entrypoints install, so it can leak a human
line into a machine-readable command. Every message belongs on the logger.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import pytest
from agentic_odi_connectors import _load_and_validate_presets

REPO_ROOT = Path(__file__).resolve().parents[3]
PACKAGE_SRC = REPO_ROOT / "packages" / "connectors" / "src" / "agentic_odi_connectors"


def test_library_code_does_not_print() -> None:
    offenders = [
        p
        for p in PACKAGE_SRC.rglob("*.py")
        if re.search(r"^\s*print\(", p.read_text(encoding="utf-8"), re.M)
    ]
    assert offenders == []


def test_malformed_config_emits_a_warning_and_nothing_else(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, capsys: pytest.CaptureFixture
) -> None:
    monkeypatch.setenv("AGENTIC_ODI_CONNECTORS_CONFIG", str(_bad_config_path()))
    caplog.set_level(logging.WARNING, logger="agentic_odi_connectors")
    with pytest.raises(SystemExit):
        _load_and_validate_presets()
    assert any("invalid connector preset" in r.message for r in caplog.records)
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def _bad_config_path() -> Path:
    return Path(__file__).resolve().parent / "data" / "malformed-connectors.json"
