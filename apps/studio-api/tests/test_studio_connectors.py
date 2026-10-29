from __future__ import annotations

import pytest
from agentic_odi_connectors.models import HealthStatus
from agentic_odi_connectors.registry import ConnectorNotFoundError
from agentic_odi_studio_api.studio.connectors import ConnectorService


def _svc(tmp_path) -> ConnectorService:
    return ConnectorService(tmp_path / "connectors.json")


def test_add_from_preset_persists(tmp_path) -> None:
    svc = _svc(tmp_path)

    config = svc.add(preset_id="notion")

    assert config.name == "notion"
    assert config.kind == "mcp"
    stored = svc.list()
    assert len(stored) == 1
    assert stored[0].name == "notion"


def test_add_custom_url_requires_name(tmp_path) -> None:
    svc = _svc(tmp_path)

    config = svc.add(name="gong", url="http://localhost:9000/mcp")

    assert config.name == "gong"
    assert config.settings["url"] == "http://localhost:9000/mcp"


def test_add_requires_preset_or_url(tmp_path) -> None:
    svc = _svc(tmp_path)

    with pytest.raises(ValueError):
        svc.add()


def test_add_url_without_name_raises(tmp_path) -> None:
    svc = _svc(tmp_path)

    with pytest.raises(ValueError):
        svc.add(url="http://localhost:9000/mcp")


def test_delete_removes_and_persists(tmp_path) -> None:
    svc = _svc(tmp_path)
    svc.add(name="gong", url="http://localhost:1/mcp")

    assert svc.delete("gong") is True
    assert svc.list() == []


def test_delete_missing_raises(tmp_path) -> None:
    svc = _svc(tmp_path)

    with pytest.raises(ConnectorNotFoundError):
        svc.delete("nope")


def test_catalog_returns_presets() -> None:
    svc = ConnectorService()

    items = svc.catalog()

    assert any(item["id"] == "notion" for item in items)
    assert items and "is_recommended" in items[0]


def test_health_runs_connector_health(monkeypatch, tmp_path) -> None:
    svc = _svc(tmp_path)
    svc.add(name="gong", preset_id="gong")

    class _Stub:
        async def health(self) -> HealthStatus:
            return HealthStatus(ok=True, message="ok", details={})

    monkeypatch.setattr(
        "agentic_odi_studio_api.studio.connectors.build_connector",
        lambda config: _Stub(),
    )

    result = svc.health("gong")

    assert result.ok is True
    assert result.message == "ok"


def test_health_missing_raises(tmp_path) -> None:
    svc = _svc(tmp_path)

    with pytest.raises(ConnectorNotFoundError):
        svc.health("nope")


def test_health_failure_returns_unhealthy(monkeypatch, tmp_path) -> None:
    svc = _svc(tmp_path)
    svc.add(name="gong", preset_id="gong")

    class _Bad:
        async def health(self) -> HealthStatus:
            raise RuntimeError("boom")

    monkeypatch.setattr(
        "agentic_odi_studio_api.studio.connectors.build_connector",
        lambda config: _Bad(),
    )

    result = svc.health("gong")

    assert result.ok is False
    assert "boom" in result.message
