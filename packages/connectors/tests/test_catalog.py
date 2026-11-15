from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from agentic_odi_connectors.catalog import (
    AREA_LABELS,
    PRESETS,
    UnknownAreaError,
    UnknownPresetError,
    connector_config_from_preset,
    get_preset,
    list_presets,
)
from agentic_odi_connectors.registry import ConnectorRegistry

ENV_REF = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def test_preset_ids_are_unique() -> None:
    ids = [preset.id for preset in PRESETS]

    assert len(ids) == len(set(ids))


def test_every_capability_area_is_covered() -> None:
    assert {preset.area for preset in PRESETS} == set(AREA_LABELS)


def test_presets_use_https_endpoints_and_docs() -> None:
    for preset in PRESETS:
        assert preset.url.startswith("https://"), preset.id
        assert preset.docs.startswith("https://"), preset.id
        assert preset.summary, preset.id


def test_interpolated_env_vars_are_declared() -> None:
    for preset in PRESETS:
        referenced = set(ENV_REF.findall(preset.url))
        for value in preset.headers.values():
            referenced |= set(ENV_REF.findall(value))

        assert referenced <= set(preset.env_vars), preset.id


def test_oauth_presets_need_no_static_credentials() -> None:
    for preset in PRESETS:
        if preset.auth == "oauth":
            assert preset.env_vars == [], preset.id
            assert preset.headers == {}, preset.id


def test_api_key_presets_declare_credentials() -> None:
    for preset in PRESETS:
        if preset.auth != "oauth":
            assert preset.env_vars, preset.id


def test_list_presets_filters_by_area() -> None:
    filtered = list_presets("knowledge-output")

    assert filtered
    assert all(preset.area == "knowledge-output" for preset in filtered)


def test_list_presets_rejects_unknown_area() -> None:
    with pytest.raises(UnknownAreaError):
        list_presets("not-an-area")


def test_get_preset_unknown_raises() -> None:
    with pytest.raises(UnknownPresetError):
        get_preset("not-a-preset")


def test_connector_config_from_preset_populates_settings() -> None:
    preset = get_preset("github")

    config = connector_config_from_preset(preset)

    assert config.name == "github"
    assert config.kind == "mcp"
    assert config.enabled is True
    assert config.settings["url"] == preset.url
    assert config.settings["env_vars"] == ["GITHUB_PERSONAL_ACCESS_TOKEN"]
    assert config.settings["headers"]["Authorization"] == ("Bearer ${GITHUB_PERSONAL_ACCESS_TOKEN}")


def test_connector_config_from_preset_allows_overrides() -> None:
    preset = get_preset("linear")

    config = connector_config_from_preset(
        preset,
        name="team-linear",
        url="http://localhost:9000/mcp",
        tools=["list_issues"],
    )

    assert config.name == "team-linear"
    assert config.settings["url"] == "http://localhost:9000/mcp"
    assert config.settings["tools"] == ["list_issues"]


def test_registry_accepts_preset_config(tmp_path: Path) -> None:
    registry = ConnectorRegistry(tmp_path / "connectors.json")

    registry.add(connector_config_from_preset(get_preset("notion")))

    stored = registry.get("notion")
    assert stored.settings["auth"] == "oauth"
    assert stored.settings["url"] == "https://mcp.notion.com/mcp"


def test_recommended_presets_are_marked() -> None:
    recommended = {preset.id for preset in PRESETS if preset.is_recommended}

    assert {"notion", "posthog", "exa", "linear", "github"} <= recommended


def test_composio_preset_is_optional_and_oauth() -> None:
    """Composio Connect's shared MCP URL is static and OAuth-authenticated.

    Composio's docs distinguish two entry points: the Composio Connect shared
    URL (``https://connect.composio.dev/mcp``, OAuth) that this preset encodes,
    and a session-scoped MCP endpoint that is minted per user
    (``POST /api/v3.1/tool_router/session``) and carries an ``x-api-key``
    header. Only the former is a static URL, so the preset must stay OAuth with
    no embedded credential.
    """
    preset = get_preset("composio")

    assert preset.label == "Composio"
    assert preset.area == "strategy-alignment"
    assert preset.url == "https://connect.composio.dev/mcp"
    assert preset.auth == "oauth"
    assert preset.env_vars == []
    assert preset.headers == {}
    assert preset.is_recommended is False
    assert preset.docs.startswith("https://")


def test_composio_config_can_be_added_without_blocking_others(tmp_path: Path) -> None:
    """A composio entry must not prevent other connectors from being registered."""
    registry = ConnectorRegistry(tmp_path / "connectors.json")

    registry.add(connector_config_from_preset(get_preset("notion")))
    registry.add(connector_config_from_preset(get_preset("composio")))

    names = {config.name for config in registry.list_all()}
    assert {"notion", "composio"} <= names


def test_composio_health_failure_does_not_block_other_connectors(tmp_path: Path) -> None:
    """Health is per-connector: a down composio connector must not hide the rest."""
    import asyncio

    from agentic_odi_connectors.factory import build_connector
    from agentic_odi_connectors.protocol import HealthStatus

    class _Broken:
        async def health(self) -> HealthStatus:
            return HealthStatus(ok=False, message="unreachable: composio down")

    class _Healthy:
        async def health(self) -> HealthStatus:
            return HealthStatus(ok=True, message="ok")

    real_build = build_connector

    def fake_build(config):
        if config.name == "composio":
            return _Broken()
        if config.name == "notion":
            return _Healthy()
        return real_build(config)

    registry = ConnectorRegistry(tmp_path / "connectors.json")
    registry.add(connector_config_from_preset(get_preset("composio")))
    registry.add(connector_config_from_preset(get_preset("notion")))

    statuses = []
    for item in registry.list_all():
        connector = fake_build(item)
        statuses.append((item.name, asyncio.run(connector.health())))

    composio_status = next(s for n, s in statuses if n == "composio")
    notion_status = next(s for n, s in statuses if n == "notion")
    assert composio_status.ok is False
    assert notion_status.ok is True


def test_list_presets_recommended_filter_returns_subset() -> None:
    full = list_presets()
    rec = list_presets(recommended=True)

    assert rec
    assert {preset.id for preset in rec} <= {preset.id for preset in full}
    assert all(preset.is_recommended for preset in rec)
    assert len(rec) < len(full)


def test_list_presets_recommended_false_returns_all() -> None:
    assert len(list_presets(recommended=False)) == len(list_presets())


def test_committed_catalog_snapshot_matches_the_code() -> None:
    """The published catalog is generated from this module; keep them in step."""
    snapshot = Path(__file__).resolve().parents[3] / "docs" / "connectors-catalog.json"
    committed = json.loads(snapshot.read_text(encoding="utf-8"))
    from_code = [preset.model_dump() for preset in list_presets()]

    assert committed == from_code, (
        "docs/connectors-catalog.json does not match the connector catalog. Regenerate it: "
        "uv run python -m agentic_odi_cli connectors catalog --json > docs/connectors-catalog.json"
    )
