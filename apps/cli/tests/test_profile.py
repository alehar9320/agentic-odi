from pathlib import Path

from agentic_odi_cli import profile


def _isolate(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.delenv("AGENTIC_ODI_BASELINE_FILE", raising=False)


def test_config_dir_uses_xdg_config_home(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    assert profile.config_dir() == tmp_path / "cfg" / "agentic-odi"


def test_config_dir_defaults_to_home(monkeypatch, tmp_path):
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    assert profile.config_dir() == Path(tmp_path) / "agentic-odi"


def test_baseline_file_location(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    assert profile.baseline_file() == tmp_path / "cfg" / "agentic-odi" / "baseline.json"


def test_baseline_file_defaults_to_home(monkeypatch, tmp_path):
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    assert profile.baseline_file() == Path(tmp_path) / "agentic-odi" / "baseline.json"


def test_baseline_exists_returns_false_when_no_file(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    assert not profile.baseline_exists()


def test_save_and_load_baseline(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    b = profile.Baseline(
        schema_version=1, source="url", product_name="Acme", product_url="https://acme.com"
    )
    saved = profile.save_baseline(b)
    assert saved == profile.config_dir() / "baseline.json"
    assert profile.baseline_exists()
    loaded = profile.load_baseline()
    assert loaded is not None
    assert loaded.schema_version == 1
    assert loaded.source == "url"
    assert loaded.product_name == "Acme"
    assert loaded.product_url == "https://acme.com"


def test_load_baseline_returns_none_without_a_file(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)

    assert profile.load_baseline() is None


def test_load_baseline_rejects_corrupt_json(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    target = profile.baseline_file()
    target.parent.mkdir(parents=True)
    target.write_text("{not json")

    try:
        profile.load_baseline()
    except ValueError as exc:
        assert "Failed to parse baseline file" in str(exc)
    else:  # pragma: no cover - corrupt JSON must raise
        raise AssertionError("expected ValueError")


def test_save_sets_created_at_when_missing(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)

    profile.save_baseline(profile.Baseline(product_name="Acme"))
    loaded = profile.load_baseline()

    assert loaded is not None
    assert loaded.created_at is not None
    assert loaded.created_at.endswith("Z")


def test_save_preserves_an_explicit_created_at(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)

    profile.save_baseline(profile.Baseline(created_at="2026-01-01T00:00:00Z"))
    loaded = profile.load_baseline()

    assert loaded is not None
    assert loaded.created_at == "2026-01-01T00:00:00Z"


def test_backup_baseline_returns_none_without_a_file(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)

    assert profile.backup_baseline() is None


def test_backup_baseline_copies_the_current_file(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    profile.save_baseline(profile.Baseline(product_name="Acme"))

    backup = profile.backup_baseline()

    assert backup is not None
    assert backup.exists()
    assert backup.name.startswith("baseline.json.bak-")
    assert backup.read_text() == profile.baseline_file().read_text()


# ---------------------------------------------------------------------------
# LLMProfile tests
# ---------------------------------------------------------------------------


def test_llm_profile_round_trips_to_disk(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    p = profile.LLMProfile(
        base_url="http://localhost:8001/v1",
        api_key="secret",
        model="my-model",
        mcp_url="http://localhost:8000/mcp",
        provider_label="Local LLM",
    )
    profile.save_llm_profile(p)
    loaded = profile.load_llm_profile()
    assert loaded is not None
    assert loaded.base_url == p.base_url
    assert loaded.api_key == p.api_key
    assert loaded.model == p.model
    assert loaded.mcp_url == p.mcp_url
    assert loaded.provider_label == p.provider_label
    assert loaded.schema_version == p.schema_version


def test_llm_profile_returns_none_when_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert profile.load_llm_profile() is None


def test_llm_profile_handles_corrupt_file(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    target = profile.llm_profile_file()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("{not valid json")

    try:
        profile.load_llm_profile()
    except ValueError as exc:
        assert "Failed to parse LLM profile file" in str(exc)
    else:  # pragma: no cover - corrupt JSON must raise
        raise AssertionError("expected ValueError")


def test_llm_profile_save_sets_timestamps(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    p = profile.LLMProfile(model="some-model")
    assert p.created_at is None
    assert p.updated_at is None

    profile.save_llm_profile(p)
    loaded = profile.load_llm_profile()

    assert loaded is not None
    assert loaded.created_at is not None
    assert loaded.created_at.endswith("Z")
    assert loaded.updated_at is not None
    assert loaded.updated_at.endswith("Z")


def test_chat_config_from_env_falls_back_to_profile(monkeypatch, tmp_path):
    # Unset all AGENTIC_ODI env vars so they don't interfere.
    for var in (
        "AGENTIC_ODI_BASE_URL",
        "AGENTIC_ODI_API_KEY",
        "AGENTIC_ODI_MODEL",
        "AGENTIC_ODI_MCP_URL",
    ):
        monkeypatch.delenv(var, raising=False)

    fake_profile = profile.LLMProfile(
        base_url="http://profile-host:9000/v1",
        api_key="profile-key",
        model="profile-model",
        mcp_url="http://profile-mcp:7000/mcp",
    )

    # Patch the function in cli.profile so the lazy import inside from_env picks it up.
    monkeypatch.setattr(profile, "load_llm_profile", lambda: fake_profile)

    from agentic_odi_cli import chat as chat_module

    config = chat_module.ChatConfig.from_env()

    assert config.base_url == "http://profile-host:9000/v1"
    assert config.api_key == "profile-key"
    assert config.model == "profile-model"
    assert config.mcp_url == "http://profile-mcp:7000/mcp"
