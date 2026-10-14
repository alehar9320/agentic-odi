import pytest
from connectors import ConnectorConfig, McpConnectorSettings
from connectors.errors import UnknownConnectorKindError


def test_mcp_settings_parse_url_and_tools():
    s = McpConnectorSettings.model_validate({"url": "http://h/mcp", "tools": ["a"]})
    assert s.url == "http://h/mcp" and s.tools == ["a"]


def test_mcp_settings_default_tools_empty():
    assert McpConnectorSettings(url="http://h/mcp").tools == []


def test_mcp_settings_returns_typed_settings():
    cfg = ConnectorConfig(name="x", kind="mcp", settings={"url": "http://h/mcp"})
    assert cfg.mcp_settings().url == "http://h/mcp"


def test_unknown_kind_raises_clear_error():
    cfg = ConnectorConfig(name="x", kind="rest", settings={})
    with pytest.raises(UnknownConnectorKindError) as ei:
        cfg.mcp_settings()
    assert "rest" in str(ei.value)
