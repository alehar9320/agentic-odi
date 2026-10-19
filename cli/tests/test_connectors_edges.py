"""Edge-case tests for the connectors CLI adapter."""

from __future__ import annotations

import json
from pathlib import Path

from connectors.models import HealthStatus
from typer.testing import CliRunner

from cli import connectors
from cli.cli import app

runner = CliRunner()


def test_lazy_wrappers_call_the_connectors_package() -> None:
    from connectors.models import ConnectorConfig

    built = connectors.build_connector(
        ConnectorConfig(name="gong", kind="mcp", settings={"url": "http://localhost:9000/mcp"})
    )
    sink = connectors.get_default_sink()

    assert built.__class__.__name__ == "MCPClientConnector"
    assert sink.__class__.__name__ == "IngestSink"


def test_config_path_prefers_the_environment(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("AGENTIC_ODI_CONNECTORS_FILE", str(tmp_path / "env.json"))

    assert connectors._config_path(None) == tmp_path / "env.json"
    assert connectors._config_path(tmp_path / "explicit.json") == tmp_path / "explicit.json"


def test_config_path_defaults_to_the_working_directory(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("AGENTIC_ODI_CONNECTORS_FILE", raising=False)
    monkeypatch.chdir(tmp_path)

    assert connectors._config_path(None) == Path.cwd() / ".agentic-odi" / "connectors.json"


def test_connector_timeout_reads_and_validates_the_environment(monkeypatch) -> None:
    monkeypatch.delenv("AGENTIC_ODI_CONNECTOR_TIMEOUT", raising=False)
    assert connectors._connector_timeout() == 30.0

    monkeypatch.setenv("AGENTIC_ODI_CONNECTOR_TIMEOUT", "2.5")
    assert connectors._connector_timeout() == 2.5

    monkeypatch.setenv("AGENTIC_ODI_CONNECTOR_TIMEOUT", "nonsense")
    assert connectors._connector_timeout() == 30.0


def test_catalog_renders_presets_without_auth(monkeypatch) -> None:
    from types import SimpleNamespace

    monkeypatch.setattr(
        "connectors.catalog.list_presets",
        lambda area: [
            SimpleNamespace(
                id="open",
                label="Open API",
                area="voice-of-customer",
                auth="none",
                env_vars=[],
                url="https://example.test/mcp",
            )
        ],
    )

    result = runner.invoke(app, ["connectors", "catalog"])

    assert result.exit_code == 0
    assert "none" in result.output
    assert "https://example.test/mcp" in result.output


def test_add_mcp_requires_a_name_when_no_preset_is_given(tmp_path) -> None:
    result = runner.invoke(
        app,
        [
            "connectors",
            "add",
            "mcp",
            "--url",
            "http://localhost:9000/mcp",
            "--config",
            str(tmp_path / "connectors.json"),
        ],
    )

    assert result.exit_code == 1
    assert "--name is required" in result.output


def test_add_mcp_stores_repeatable_tools(tmp_path) -> None:
    config = tmp_path / "connectors.json"

    result = runner.invoke(
        app,
        [
            "connectors",
            "add",
            "mcp",
            "--name",
            "gong",
            "--url",
            "http://localhost:9000/mcp",
            "--tool",
            "list_calls",
            "--tool",
            "get_call",
            "--config",
            str(config),
        ],
    )

    assert result.exit_code == 0
    stored = json.loads(config.read_text())["connectors"][0]
    assert stored["settings"]["tools"] == ["list_calls", "get_call"]


def test_add_unknown_kind_requires_a_name(tmp_path) -> None:
    result = runner.invoke(
        app,
        ["connectors", "add", "rest", "--config", str(tmp_path / "connectors.json")],
    )

    assert result.exit_code == 1
    assert "--name is required." in result.output


def test_health_reports_unknown_connectors(tmp_path) -> None:
    result = runner.invoke(
        app,
        ["connectors", "health", "--name", "missing", "--config", str(tmp_path / "c.json")],
    )

    assert result.exit_code == 1
    assert "Connector not found" in result.output


def test_ingest_reports_unknown_connectors(tmp_path) -> None:
    result = runner.invoke(
        app,
        ["connectors", "ingest", "--name", "missing", "--config", str(tmp_path / "c.json")],
    )

    assert result.exit_code == 1
    assert "Connector not found" in result.output


class _Unhealthy:
    async def health(self) -> HealthStatus:
        return HealthStatus(ok=False, message="unreachable")


def test_health_exits_nonzero_when_the_connector_is_unhealthy(tmp_path, monkeypatch) -> None:
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
    monkeypatch.setattr(connectors, "build_connector", lambda _config: _Unhealthy())

    result = runner.invoke(app, ["connectors", "health", "--name", "gong", "--config", str(config)])

    assert result.exit_code == 1
    assert '"ok":false' in result.output
