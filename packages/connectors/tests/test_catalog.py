from __future__ import annotations

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


def test_list_presets_recommended_filter_returns_subset() -> None:
    full = list_presets()
    rec = list_presets(recommended=True)

    assert rec
    assert {preset.id for preset in rec} <= {preset.id for preset in full}
    assert all(preset.is_recommended for preset in rec)
    assert len(rec) < len(full)


def test_list_presets_recommended_false_returns_all() -> None:
    assert len(list_presets(recommended=False)) == len(list_presets())
