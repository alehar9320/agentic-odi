from __future__ import annotations

import pytest
from agentic_odi_connectors import ConfigurationError, validate_connector_config


def test_valid_config_passes_unchanged() -> None:
    config = {
        "kind": "rest",
        "health_url": "https://example.com/health",
        "ingest_endpoint": "https://example.com/ingest",
    }
    assert validate_connector_config(config) == config


def test_valid_config_in_memory() -> None:
    config = {
        "kind": "in_memory",
        "health_url": "http://localhost:9000/health",
        "ingest_endpoint": "http://localhost:9000/ingest",
    }
    assert validate_connector_config(config) == config


def test_valid_config_mcp() -> None:
    config = {
        "kind": "mcp",
        "health_url": "https://mcp.example.com/health",
        "ingest_endpoint": "https://mcp.example.com/ingest",
    }
    assert validate_connector_config(config) == config


def test_missing_kind_raises() -> None:
    config = {
        "health_url": "https://example.com/health",
        "ingest_endpoint": "https://example.com/ingest",
    }
    with pytest.raises(ConfigurationError) as exc_info:
        validate_connector_config(config)
    assert "kind" in exc_info.value.keys


def test_missing_health_url_raises() -> None:
    config = {
        "kind": "rest",
        "ingest_endpoint": "https://example.com/ingest",
    }
    with pytest.raises(ConfigurationError) as exc_info:
        validate_connector_config(config)
    assert "health_url" in exc_info.value.keys


def test_missing_ingest_endpoint_raises() -> None:
    config = {
        "kind": "rest",
        "health_url": "https://example.com/health",
    }
    with pytest.raises(ConfigurationError) as exc_info:
        validate_connector_config(config)
    assert "ingest_endpoint" in exc_info.value.keys


def test_invalid_kind_raises() -> None:
    config = {
        "kind": "salesforce",
        "health_url": "https://example.com/health",
        "ingest_endpoint": "https://example.com/ingest",
    }
    with pytest.raises(ConfigurationError) as exc_info:
        validate_connector_config(config)
    assert "kind" in exc_info.value.keys


def test_malformed_health_url_raises() -> None:
    config = {
        "kind": "rest",
        "health_url": "ftp://example.com/health",
        "ingest_endpoint": "https://example.com/ingest",
    }
    with pytest.raises(ConfigurationError) as exc_info:
        validate_connector_config(config)
    assert "health_url" in exc_info.value.keys


def test_empty_ingest_endpoint_raises() -> None:
    config = {
        "kind": "rest",
        "health_url": "https://example.com/health",
        "ingest_endpoint": "",
    }
    with pytest.raises(ConfigurationError) as exc_info:
        validate_connector_config(config)
    assert "ingest_endpoint" in exc_info.value.keys


def test_multiple_invalid_keys_reported() -> None:
    config = {
        "kind": "salesforce",
        "health_url": "not-a-url",
    }
    with pytest.raises(ConfigurationError) as exc_info:
        validate_connector_config(config)
    assert set(exc_info.value.keys) == {"kind", "health_url", "ingest_endpoint"}
