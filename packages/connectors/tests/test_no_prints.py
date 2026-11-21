"""No library code in the connectors package prints to stdout or stderr.

The package is imported by the CLI, the sidecar, and the MCP server, each of
which configures logging differently. A bare ``print`` bypasses the level, the
handler, and the redaction the entrypoints install, so it can leak a human
line into a machine-readable command. Every message belongs on the logger.
"""

from __future__ import annotations

import contextlib
import logging
import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from agentic_odi_connectors import _load_and_validate_presets
from agentic_odi_connectors.paths import CONFIG_PATH_ENV

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
    monkeypatch.setenv(
        "AGENTIC_ODI_CONNECTORS_CONFIG",
        str(Path(__file__).resolve().parent / "data" / "malformed-connectors.json"),
    )
    with _captured(caplog, expected="invalid connector preset"):
        with pytest.raises(SystemExit):
            _load_and_validate_presets()
    _assert_streams_silent(capsys)


def test_unreadable_config_warns_and_exits(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture,
) -> None:
    _point_at(monkeypatch, tmp_path, "{not json")
    with _captured(caplog, expected="could not read connectors config"):
        with pytest.raises(SystemExit):
            _load_and_validate_presets()
    _assert_streams_silent(capsys)


def test_non_list_connectors_warns_and_exits(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture,
) -> None:
    _point_at(monkeypatch, tmp_path, '{"connectors": {}}')
    with _captured(caplog, expected="must contain a 'connectors' list"):
        with pytest.raises(SystemExit):
            _load_and_validate_presets()
    _assert_streams_silent(capsys)


def test_valid_config_warns_nothing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    _point_at(
        monkeypatch,
        tmp_path,
        '{"connectors": [{"name": "prod", "kind": "rest", '
        '"health_url": "https://example.com/health", '
        '"ingest_endpoint": "https://example.com/ingest"}]}',
    )
    with _captured(caplog):
        _load_and_validate_presets()


def test_missing_config_file_is_silent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv(CONFIG_PATH_ENV, str(tmp_path / "absent.json"))
    with _captured(caplog):
        _load_and_validate_presets()


@contextlib.contextmanager
def _captured(caplog: pytest.LogCaptureFixture, expected: str | None = None) -> Iterator[None]:
    """Capture this module's warnings with the root logger isolated.

    A prior test (the CLI suite calls ``configure_logging``) can leave a root
    handler bound to a stream pytest has since closed. When a warning
    propagates to that stale handler the stdlib prints a "Logging error"
    traceback to the *current* stderr, which would fail the stream assertions.
    """
    caplog.set_level(logging.WARNING, logger="agentic_odi_connectors")
    root = logging.getLogger()
    stale_handlers = root.handlers[:]
    root.handlers = [caplog.handler]
    try:
        yield
    finally:
        root.handlers = stale_handlers
    messages = [record.getMessage() for record in caplog.records]
    if expected is None:
        assert messages == []
    else:
        assert any(expected in message for message in messages)


def _point_at(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, body: str) -> None:
    config = tmp_path / "connectors.json"
    config.write_text(body, encoding="utf-8")
    monkeypatch.setenv(CONFIG_PATH_ENV, str(config))


def _assert_streams_silent(capsys: pytest.CaptureFixture) -> None:
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
