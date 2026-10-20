from core import InMemoryRepository, build_repository
from core.sqlite_repository import SQLiteRepository


def test_memory_path_returns_in_memory(monkeypatch):
    monkeypatch.setenv("AGENTIC_ODI_DB", ":memory:")
    assert isinstance(build_repository(), InMemoryRepository)


def test_default_path_returns_sqlite(tmp_path, monkeypatch):
    monkeypatch.delenv("AGENTIC_ODI_DB", raising=False)
    repo = build_repository(db_path=str(tmp_path / "odi.db"))
    assert isinstance(repo, SQLiteRepository)


def test_explicit_db_path_wins_over_env_var(tmp_path, monkeypatch):
    env_path = tmp_path / "env.db"
    explicit_path = tmp_path / "odi.db"
    monkeypatch.setenv("AGENTIC_ODI_DB", str(env_path))
    repo = build_repository(db_path=str(explicit_path))
    assert isinstance(repo, SQLiteRepository)
    assert explicit_path.exists()
    assert not env_path.exists()


def test_env_var_resolution(tmp_path, monkeypatch):
    env_path = tmp_path / "e.db"
    monkeypatch.setenv("AGENTIC_ODI_DB", str(env_path))
    repo = build_repository()
    assert isinstance(repo, SQLiteRepository)
    assert env_path.exists()


def test_default_is_home_store_and_parent_created(tmp_path, monkeypatch):
    monkeypatch.delenv("AGENTIC_ODI_DB", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    repo = build_repository()
    assert isinstance(repo, SQLiteRepository)
    assert (tmp_path / ".agentic-odi" / "odi.db").exists()
