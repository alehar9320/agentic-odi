from __future__ import annotations

import json
import re
from pathlib import Path
from unittest.mock import MagicMock

from typer.testing import CliRunner

from cli.cli import app
from connectors.models import HealthStatus, IngestBatch, IngestRecord

ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")
runner = CliRunner()


def _strip(text: str) -> str:
    return ANSI_ESCAPE.sub("", text)


def test_connectors_help_lists_commands() -> None:
    result = runner.invoke(app, ["connectors", "--help"])

    assert result.exit_code == 0
    output = _strip(result.output)
    assert "list" in output
    assert "add" in output
    assert "health" in output
    assert "ingest" in output


def test_connectors_list_empty(tmp_path: Path) -> None:
    config = tmp_path / "connectors.json"
    result = runner.invoke(app, ["connectors", "list", "--config", str(config)])

    assert result.exit_code == 0
    assert "No connectors configured." in _strip(result.output)


def test_connectors_add_mcp_then_list(tmp_path: Path) -> None:
    config = tmp_path / "connectors.json"
    add = runner.invoke(
        app,
        [
            "connectors",
            "add",
            "mcp",
            "--name",
            "gong",
            "--url",
            "http://localhost:9000/mcp",
            "--config",
            str(config),
        ],
    )
    listed = runner.invoke(app, ["connectors", "list", "--config", str(config)])

    assert add.exit_code == 0
    assert listed.exit_code == 0
    assert "gong" in _strip(listed.output)
    assert "mcp" in _strip(listed.output)
    payload = json.loads(config.read_text(encoding="utf-8"))
    assert payload["connectors"][0]["settings"]["url"] == "http://localhost:9000/mcp"


def test_connectors_add_rejects_duplicate(tmp_path: Path) -> None:
    config = tmp_path / "connectors.json"
    args = [
        "connectors",
        "add",
        "mcp",
        "--name",
        "gong",
        "--url",
        "http://localhost:9000/mcp",
        "--config",
        str(config),
    ]
    runner.invoke(app, args)
    result = runner.invoke(app, args)

    assert result.exit_code == 1
    assert "already exists" in _strip(result.output)


def test_connectors_add_rejects_unknown_kind(tmp_path: Path) -> None:
    config = tmp_path / "connectors.json"
    result = runner.invoke(
        app,
        ["connectors", "add", "rest", "--name", "jira", "--config", str(config)],
    )

    assert result.exit_code == 1
    assert "Unknown connector kind" in _strip(result.output)


def test_connectors_add_mcp_requires_url(tmp_path: Path) -> None:
    config = tmp_path / "connectors.json"
    result = runner.invoke(
        app,
        ["connectors", "add", "mcp", "--name", "gong", "--config", str(config)],
    )

    assert result.exit_code == 1
    assert "--url is required" in _strip(result.output)


class _FakeConnector:
    def __init__(self, batch: IngestBatch | None = None) -> None:
        self.batch = batch or IngestBatch(connector_name="gong")

    async def health(self) -> HealthStatus:
        return HealthStatus(ok=True, message="reachable")

    async def ingest(self) -> IngestBatch:
        return self.batch


def test_connectors_health_uses_built_connector(tmp_path: Path, monkeypatch) -> None:
    config = tmp_path / "connectors.json"
    runner.invoke(
        app,
        [
            "connectors",
            "add",
            "mcp",
            "--name",
            "gong",
            "--url",
            "http://localhost:9000/mcp",
            "--config",
            str(config),
        ],
    )
    monkeypatch.setattr("cli.connectors.build_connector", lambda _config: _FakeConnector())

    result = runner.invoke(
        app, ["connectors", "health", "--name", "gong", "--config", str(config)]
    )

    assert result.exit_code == 0
    assert "reachable" in _strip(result.output)


def test_connectors_ingest_appends_to_sink(tmp_path: Path, monkeypatch) -> None:
    config = tmp_path / "connectors.json"
    runner.invoke(
        app,
        [
            "connectors",
            "add",
            "mcp",
            "--name",
            "gong",
            "--url",
            "http://localhost:9000/mcp",
            "--config",
            str(config),
        ],
    )
    batch = IngestBatch(
        connector_name="gong",
        records=[
            IngestRecord(
                source_name="gong",
                source_kind="mcp",
                item_type="catalog",
                name="mcp-catalog",
                content="{}",
            )
        ],
    )
    sink = MagicMock()
    monkeypatch.setattr(
        "cli.connectors.build_connector", lambda _config: _FakeConnector(batch)
    )
    monkeypatch.setattr("cli.connectors.get_default_sink", lambda: sink)

    result = runner.invoke(
        app, ["connectors", "ingest", "--name", "gong", "--config", str(config)]
    )

    assert result.exit_code == 0
    sink.append.assert_called_once()
    assert "gong" in _strip(result.output)
