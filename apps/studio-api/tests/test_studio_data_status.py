"""Metadata-only status for the sidecar's two SQLite stores.

`GET /api/data/status` reports the resolved path, byte size, and modification
time of the ODI and Studio databases without returning any entity rows or
credentials.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from agentic_odi_core.sqlite_repository import SQLiteRepository
from agentic_odi_studio_api.app import create_app
from agentic_odi_studio_api.studio.memory import StudioMemory
from fastapi.testclient import TestClient


def _make_client(
    tmp_path: Path, monkeypatch, odi_path: Path | None = None, studio_path: Path | None = None
) -> TestClient:
    odi_path = odi_path or tmp_path / "odi.db"
    studio_path = studio_path or tmp_path / "studio.db"
    monkeypatch.setenv("AGENTIC_ODI_DB", str(odi_path))
    monkeypatch.setenv("AGENTIC_ODI_STUDIO_DB", str(studio_path))
    repo = SQLiteRepository(str(odi_path))
    memory = StudioMemory(str(studio_path))
    return TestClient(create_app(repo, memory=memory, backend="local"))


def _parse_instant(value: str | None) -> datetime:
    assert value is not None, "expected a modification timestamp"
    return datetime.fromisoformat(value)


def test_data_status_reports_both_stores_with_resolved_paths(tmp_path: Path, monkeypatch) -> None:
    client = _make_client(tmp_path, monkeypatch)

    response = client.get("/api/data/status")

    assert response.status_code == 200
    body = response.json()
    stores = body["stores"]
    assert [store["id"] for store in stores] == ["odi", "studio"]

    odi = stores[0]
    assert odi["id"] == "odi"
    assert odi["path"] == str(tmp_path / "odi.db")
    assert isinstance(odi["bytes"], int) and odi["bytes"] >= 0
    _parse_instant(odi["lastModified"])

    studio = stores[1]
    assert studio["id"] == "studio"
    assert studio["path"] == str(tmp_path / "studio.db")
    assert isinstance(studio["bytes"], int) and studio["bytes"] >= 0
    _parse_instant(studio["lastModified"])


def test_data_status_honours_each_environment_override_independently(
    tmp_path: Path, monkeypatch
) -> None:
    custom_odi = tmp_path / "custom" / "odi.db"
    custom_studio = tmp_path / "custom" / "studio.db"
    client = _make_client(tmp_path, monkeypatch, odi_path=custom_odi, studio_path=custom_studio)

    body = client.get("/api/data/status").json()
    paths = {store["id"]: store["path"] for store in body["stores"]}
    assert paths["odi"] == str(custom_odi)
    assert paths["studio"] == str(custom_studio)


def test_data_status_reports_missing_file_as_unavailable_not_zero(
    tmp_path: Path, monkeypatch
) -> None:
    client = _make_client(tmp_path, monkeypatch)
    odi_file = tmp_path / "odi.db"
    assert odi_file.is_file()
    odi_file.unlink()

    body = client.get("/api/data/status").json()
    stores = {store["id"]: store for store in body["stores"]}

    assert stores["odi"]["path"] == str(odi_file)
    assert stores["odi"]["bytes"] is None
    assert stores["odi"]["lastModified"] is None

    # The studio store still exists and reports real values.
    assert stores["studio"]["bytes"] is not None
    assert stores["studio"]["lastModified"] is not None
