from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from unittest.mock import MagicMock

from agentic_odi_cli.cli import app
from agentic_odi_connectors.models import (
    HealthStatus,
    IngestBatch,
    IngestRecord,
    RestConnectorSettings,
)
from agentic_odi_connectors.rest.connector import RestConnector
from typer.testing import CliRunner

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
    assert "catalog" in output
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


def test_connectors_add_rest_with_headers(tmp_path: Path) -> None:
    config = tmp_path / "connectors.json"
    result = runner.invoke(
        app,
        [
            "connectors",
            "add",
            "rest",
            "--name",
            "jira",
            "--url",
            "https://jira.example/api/issues",
            "--header",
            "Authorization=Bearer token",
            "--records-key",
            "result.issues",
            "--config",
            str(config),
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(config.read_text(encoding="utf-8"))
    settings = payload["connectors"][0]["settings"]
    assert settings["url"] == "https://jira.example/api/issues"
    assert settings["headers"] == {"Authorization": "Bearer token"}
    assert settings["records_key"] == "result.issues"


def test_connectors_add_rejects_bad_header(tmp_path: Path) -> None:
    config = tmp_path / "connectors.json"
    result = runner.invoke(
        app,
        [
            "connectors",
            "add",
            "rest",
            "--name",
            "jira",
            "--url",
            "https://jira.example/api/issues",
            "--header",
            "broken",
            "--config",
            str(config),
        ],
    )

    assert result.exit_code == 1
    assert "KEY=VALUE" in _strip(result.output)


def test_connectors_add_rejects_unknown_kind(tmp_path: Path) -> None:
    config = tmp_path / "connectors.json"
    result = runner.invoke(
        app,
        [
            "connectors",
            "add",
            "salesforce",
            "--name",
            "crm",
            "--url",
            "https://example.test",
            "--config",
            str(config),
        ],
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


def test_connectors_catalog_groups_presets_by_area() -> None:
    result = runner.invoke(app, ["connectors", "catalog"])

    assert result.exit_code == 0
    output = _strip(result.output)
    assert "voice-of-customer" in output
    assert "market-intelligence" in output
    assert "notion" in output
    assert "tavily" in output
    assert "GITHUB_PERSONAL_ACCESS_TOKEN" in output


def test_connectors_catalog_json_lists_every_area() -> None:
    result = runner.invoke(app, ["connectors", "catalog", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert {item["area"] for item in payload} == {
        "voice-of-customer",
        "quantitative-data",
        "market-intelligence",
        "strategy-alignment",
        "knowledge-output",
    }
    assert all(item["url"].startswith("https://") for item in payload)


def test_connectors_catalog_filters_by_area() -> None:
    result = runner.invoke(app, ["connectors", "catalog", "--area", "strategy-alignment"])

    assert result.exit_code == 0
    output = _strip(result.output)
    assert "linear" in output
    assert "notion" not in output


def test_connectors_catalog_rejects_unknown_area() -> None:
    result = runner.invoke(app, ["connectors", "catalog", "--area", "nope"])

    assert result.exit_code == 1
    assert "Unknown capability area" in _strip(result.output)


def test_connectors_add_from_preset(tmp_path: Path) -> None:
    config = tmp_path / "connectors.json"

    result = runner.invoke(
        app,
        ["connectors", "add", "mcp", "--preset", "github", "--config", str(config)],
    )

    assert result.exit_code == 0
    output = _strip(result.output)
    assert "Added mcp connector 'github'" in output
    assert "GITHUB_PERSONAL_ACCESS_TOKEN" in output
    payload = json.loads(config.read_text(encoding="utf-8"))
    stored = payload["connectors"][0]
    assert stored["name"] == "github"
    assert stored["settings"]["url"] == "https://api.githubcopilot.com/mcp/"
    assert stored["settings"]["env_vars"] == ["GITHUB_PERSONAL_ACCESS_TOKEN"]
    assert stored["settings"]["headers"]["Authorization"].startswith("Bearer ")


def test_connectors_add_from_preset_with_name_override(tmp_path: Path) -> None:
    config = tmp_path / "connectors.json"

    result = runner.invoke(
        app,
        [
            "connectors",
            "add",
            "mcp",
            "--preset",
            "notion",
            "--name",
            "voice-of-customer",
            "--config",
            str(config),
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(config.read_text(encoding="utf-8"))
    stored = payload["connectors"][0]
    assert stored["name"] == "voice-of-customer"
    assert stored["settings"]["auth"] == "oauth"


def test_connectors_add_rejects_unknown_preset(tmp_path: Path) -> None:
    config = tmp_path / "connectors.json"

    result = runner.invoke(
        app,
        ["connectors", "add", "mcp", "--preset", "nope", "--config", str(config)],
    )

    assert result.exit_code == 1
    assert "Unknown preset" in _strip(result.output)


def test_connectors_add_preset_requires_mcp_kind(tmp_path: Path) -> None:
    config = tmp_path / "connectors.json"

    result = runner.invoke(
        app,
        ["connectors", "add", "rest", "--preset", "notion", "--config", str(config)],
    )

    assert result.exit_code == 1
    assert "only supported for MCP connectors" in _strip(result.output)


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
    monkeypatch.setattr(
        "agentic_odi_cli.connectors.build_connector", lambda _config: _FakeConnector()
    )

    result = runner.invoke(app, ["connectors", "health", "--name", "gong", "--config", str(config)])

    assert result.exit_code == 0
    assert "reachable" in _strip(result.output)


def test_connectors_health_no_cache_forces_a_fresh_check(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AGENTIC_ODI_CONNECTORS_CACHE", str(tmp_path / "connector-health.json"))
    config = tmp_path / "connectors.json"
    runner.invoke(
        app,
        [
            "connectors",
            "add",
            "rest",
            "--name",
            "jira",
            "--url",
            "https://api.example/records",
            "--config",
            str(config),
        ],
    )
    calls: list[str] = []

    def fetch(method, url, headers, body, timeout):
        calls.append(url)
        return 200, b"{}"

    connector = RestConnector(
        name="jira",
        settings=RestConnectorSettings(url="https://api.example/records"),
        fetcher=fetch,
    )
    monkeypatch.setattr("agentic_odi_cli.connectors.build_connector", lambda _config: connector)

    first = runner.invoke(app, ["connectors", "health", "--name", "jira", "--config", str(config)])
    cached = runner.invoke(app, ["connectors", "health", "--name", "jira", "--config", str(config)])
    fresh = runner.invoke(
        app,
        ["connectors", "health", "--name", "jira", "--no-cache", "--config", str(config)],
    )

    assert first.exit_code == cached.exit_code == fresh.exit_code == 0
    assert len(calls) == 2


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
                item_type="resource",
                name="Call notes",
                content="Onboarding is slow",
            )
        ],
    )
    sink = MagicMock()
    monkeypatch.setattr(
        "agentic_odi_cli.connectors.build_connector", lambda _config: _FakeConnector(batch)
    )
    monkeypatch.setattr("agentic_odi_cli.connectors.get_default_sink", lambda: sink)

    result = runner.invoke(app, ["connectors", "ingest", "--name", "gong", "--config", str(config)])

    assert result.exit_code == 0
    sink.append.assert_called_once()
    assert "gong" in _strip(result.output)


class _SlowConnector:
    async def health(self) -> HealthStatus:
        await asyncio.sleep(5)
        return HealthStatus(ok=True, message="reachable")


def test_connectors_health_times_out(tmp_path: Path, monkeypatch) -> None:
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
    monkeypatch.setattr(
        "agentic_odi_cli.connectors.build_connector", lambda _config: _SlowConnector()
    )
    monkeypatch.setenv("AGENTIC_ODI_CONNECTOR_TIMEOUT", "0.05")

    result = runner.invoke(app, ["connectors", "health", "--name", "gong", "--config", str(config)])

    assert result.exit_code == 1
    assert "timed out" in _strip(result.output)


def test_connectors_ingest_maps_records_to_evidence(tmp_path: Path, monkeypatch) -> None:
    config = tmp_path / "connectors.json"
    db = str(tmp_path / "odi.db")
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
    job_result = runner.invoke(app, ["--db", db, "jobs", "add", "--name", "Job", "--json"])
    job_id = json.loads(job_result.output)["id"]
    batch = IngestBatch(
        connector_name="gong",
        records=[
            IngestRecord(
                source_name="gong",
                source_kind="mcp",
                item_type="catalog",
                name="mcp-catalog",
                content="{}",
            ),
            IngestRecord(
                source_name="gong",
                source_kind="mcp",
                item_type="resource",
                name="feedback",
                content="Onboarding is slow",
            ),
        ],
    )
    monkeypatch.setattr(
        "agentic_odi_cli.connectors.build_connector", lambda _config: _FakeConnector(batch)
    )

    result = runner.invoke(
        app,
        [
            "--db",
            db,
            "connectors",
            "ingest",
            "--name",
            "gong",
            "--job-id",
            job_id,
            "--config",
            str(config),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Evidence created" in result.output
    listed = runner.invoke(app, ["--db", db, "evidence", "list", "--job-id", job_id, "--json"])
    payload = json.loads(listed.output)
    assert [item["content"] for item in payload] == ["Onboarding is slow"]
    assert all(item["name"] != "mcp-catalog" for item in payload)


def test_connectors_ingest_dry_run_writes_nothing(tmp_path: Path, monkeypatch) -> None:
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
                content="{/}",
            ),
            IngestRecord(
                source_name="gong",
                source_kind="mcp",
                item_type="catalog",
                name="second",
                content="{}",
            ),
        ],
    )
    sink = MagicMock()
    monkeypatch.setattr(
        "agentic_odi_cli.connectors.build_connector", lambda _config: _FakeConnector(batch)
    )
    monkeypatch.setattr("agentic_odi_cli.connectors.get_default_sink", lambda: sink)

    result = runner.invoke(
        app,
        ["connectors", "ingest", "--name", "gong", "--dry-run", "--config", str(config)],
    )

    assert result.exit_code == 0
    sink.append.assert_not_called()
    preview = json.loads(_strip(result.output))
    assert preview["dry_run"] is True
    assert preview["connector"] == "gong"
    assert preview["records"] == 2
    assert preview["sample"]["name"] == "mcp-catalog"
    assert "evidence_drafts" not in preview


def test_connectors_ingest_dry_run_counts_evidence_drafts(tmp_path: Path, monkeypatch) -> None:
    config = tmp_path / "connectors.json"
    db = str(tmp_path / "odi.db")
    runner.invoke(
        app,
        [
            "--db",
            db,
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
                item_type="resource",
                name="Call notes",
                content="Onboarding is slow",
            )
        ],
    )
    sink = MagicMock()
    monkeypatch.setattr(
        "agentic_odi_cli.connectors.build_connector", lambda _config: _FakeConnector(batch)
    )
    monkeypatch.setattr("agentic_odi_cli.connectors.get_default_sink", lambda: sink)

    result = runner.invoke(
        app,
        [
            "--db",
            db,
            "connectors",
            "ingest",
            "--name",
            "gong",
            "--job-id",
            "JOB-1",
            "--dry-run",
            "--config",
            str(config),
        ],
    )

    assert result.exit_code == 0
    sink.append.assert_not_called()
    preview = json.loads(_strip(result.output))
    assert preview["records"] == 1
    assert preview["evidence_drafts"] == 1


def test_connectors_list_json_prints_expected_fields(tmp_path: Path) -> None:
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

    result = runner.invoke(app, ["connectors", "list", "--config", str(config), "--json"])

    assert result.exit_code == 0
    payload = json.loads(_strip(result.output))
    assert isinstance(payload, list)
    assert payload == [
        {
            "name": "gong",
            "kind": "mcp",
            "url": "http://localhost:9000/mcp",
            "enabled": True,
        }
    ]


def test_connectors_list_json_is_an_empty_array(tmp_path: Path) -> None:
    config = tmp_path / "connectors.json"

    result = runner.invoke(app, ["connectors", "list", "--config", str(config), "--json"])

    assert result.exit_code == 0
    assert json.loads(_strip(result.output)) == []
