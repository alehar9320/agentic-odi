import os
import sys
from pathlib import Path

import pytest
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
    except profile.ProfileFileError as exc:
        assert "is not valid JSON" in str(exc)
        assert "line" in str(exc)
        assert "column" in str(exc)
        assert str(target) in str(exc)
    else:  # pragma: no cover - corrupt JSON must raise
        raise AssertionError("expected ProfileFileError")


def test_load_baseline_unreadable_file_reports_permission_not_parse(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    target = profile.baseline_file()
    target.parent.mkdir(parents=True)
    target.write_text('{"product_name": "Acme"}')
    if sys.platform != "win32" and os.geteuid() != 0:
        os.chmod(target, 0o000)
    try:
        try:
            profile.load_baseline()
        except profile.ProfileFileError as exc:
            msg = str(exc)
            assert "Could not read" in msg
            assert "parse" not in msg.lower()
            assert str(target) in msg
        else:  # pragma: no cover - unreadable file must raise
            if sys.platform == "win32" or os.geteuid() == 0:
                pytest.skip("Cannot test unreadable file as root or on Windows")
            raise AssertionError("expected ProfileFileError")
    finally:
        if sys.platform != "win32" and os.geteuid() != 0:
            os.chmod(target, 0o644)


def test_from_dict_rejects_unknown_keys(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    try:
        profile.Baseline.from_dict({"product_name": "Acme", "made_up_field": 1})
    except ValueError as exc:
        assert "made_up_field" in str(exc)
        assert "valid fields" in str(exc)
    else:  # pragma: no cover - unknown keys must raise
        raise AssertionError("expected ValueError for unknown keys")


def test_from_dict_accepts_known_keys(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    b = profile.Baseline.from_dict({"product_name": "Acme", "schema_version": 1, "source": "url"})
    assert b.product_name == "Acme"
    assert b.schema_version == 1
    assert b.source == "url"
    assert b.inferred is False


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


def test_inferred_survives_a_save_and_load(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    profile.save_baseline(
        profile.Baseline(schema_version=1, source="wizard", product_name="Acme", inferred=True)
    )
    loaded = profile.load_baseline()
    assert loaded is not None
    assert loaded.inferred is True
    assert loaded.schema_version == 1


def test_inferred_defaults_to_false_through_a_save_and_load(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    profile.save_baseline(profile.Baseline(product_name="Acme"))
    loaded = profile.load_baseline()
    assert loaded is not None
    assert loaded.inferred is False


def test_a_baseline_written_before_inferred_existed_still_loads(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    target = profile.baseline_file()
    target.parent.mkdir(parents=True)
    target.write_text('{"schema_version": 1, "product_name": "Acme"}')

    loaded = profile.load_baseline()

    assert loaded is not None
    assert loaded.product_name == "Acme"
    assert loaded.inferred is False
    assert loaded.schema_version == 1


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


def _make_backups(monkeypatch, tmp_path, stamps: list[str]) -> list[Path]:
    """Write one backup per stamp and return the paths, oldest first."""
    _isolate(monkeypatch, tmp_path)
    profile.save_baseline(profile.Baseline(product_name="Acme"))
    cfg = profile.config_dir()
    cfg.mkdir(parents=True, exist_ok=True)
    paths = []
    for stamp in stamps:
        p = cfg / f"baseline.json.bak-{stamp}"
        p.write_text("{}")
        paths.append(p)
    return paths


def test_prune_keeps_the_newest_n(monkeypatch, tmp_path):
    stamps = [f"2026010{i}T000000Z" for i in range(1, 9)]
    _make_backups(monkeypatch, tmp_path, stamps)

    removed = profile.prune_baseline_backups(keep=3)

    remaining = sorted(p.name for p in profile.config_dir().glob("baseline.json.bak-*"))
    assert len(remaining) == 3
    assert remaining == sorted(f"baseline.json.bak-{s}" for s in stamps[-3:])
    assert sorted(p.name for p in removed) == sorted(f"baseline.json.bak-{s}" for s in stamps[:5])


def test_prune_never_removes_the_new_copy(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    profile.save_baseline(profile.Baseline(product_name="Acme"))

    for i in range(1, 9):
        monkeypatch.setattr(profile, "_backup_timestamp", lambda i=i: f"2026060{i}T000000Z")
        profile.backup_baseline()

    newest = profile.config_dir() / "baseline.json.bak-20260608T000000Z"
    assert newest.exists()
    assert len(list(profile.config_dir().glob("baseline.json.bak-*"))) == (
        profile.BASELINE_BACKUP_KEEP
    )


def test_a_failed_unlink_does_not_raise(monkeypatch, tmp_path):
    stamps = [f"2026010{i}T000000Z" for i in range(1, 9)]
    _make_backups(monkeypatch, tmp_path, stamps)

    def boom(self, *args, **kwargs):
        raise OSError("locked")

    monkeypatch.setattr(Path, "unlink", boom)

    assert profile.prune_baseline_backups(keep=3) == []


def test_keep_zero_is_a_no_op(monkeypatch, tmp_path):
    stamps = [f"2026010{i}T000000Z" for i in range(1, 9)]
    _make_backups(monkeypatch, tmp_path, stamps)

    assert profile.prune_baseline_backups(keep=0) == []
    assert len(list(profile.config_dir().glob("baseline.json.bak-*"))) == 8


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
    except profile.ProfileFileError as exc:
        assert "is not valid JSON" in str(exc)
        assert "line" in str(exc)
        assert "column" in str(exc)
        assert str(target) in str(exc)
    else:  # pragma: no cover - corrupt JSON must raise
        raise AssertionError("expected ProfileFileError")


def test_llm_profile_unreadable_file_reports_permission_not_parse(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    target = profile.llm_profile_file()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text('{"model": "test"}')
    if sys.platform != "win32" and os.geteuid() != 0:
        os.chmod(target, 0o000)
    try:
        try:
            profile.load_llm_profile()
        except profile.ProfileFileError as exc:
            msg = str(exc)
            assert "Could not read" in msg
            assert "parse" not in msg.lower()
            assert str(target) in msg
        else:  # pragma: no cover - unreadable file must raise
            if sys.platform == "win32" or os.geteuid() == 0:
                pytest.skip("Cannot test unreadable file as root or on Windows")
            raise AssertionError("expected ProfileFileError")
    finally:
        if sys.platform != "win32" and os.geteuid() != 0:
            os.chmod(target, 0o644)


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


def test_llm_profile_round_trips_non_ascii(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    profile.save_llm_profile(
        profile.LLMProfile(model="münchen-7b", base_url="http://localhost:8001/v1")
    )
    assert profile.load_llm_profile().model == "münchen-7b"
