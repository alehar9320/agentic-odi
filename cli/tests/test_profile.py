from pathlib import Path

from cli import profile


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
