"""Boot integrity and clean-shutdown tests for the Studio sidecar (issue #598).

The sidecar owns two SQLite files: the ODI store and the conversation memory.
A damaged file must reach the person as a structured failure with a path to the
backup, and a clean stop must checkpoint and close both so no write-ahead log is
left for the next process to recover.
"""

from __future__ import annotations

import os

import pytest
from agentic_odi_core.errors import StoreCorrupt
from agentic_odi_core.intent_store import IntentStore
from agentic_odi_studio_api.app import checkpoint_seconds, create_app
from agentic_odi_studio_api.studio.memory import StudioMemory
from fastapi.testclient import TestClient


def _corrupt_page(path: str) -> None:
    with open(path, "r+b") as handle:
        handle.seek(4096 * 2)
        handle.write(b"\xde\xad\xbe\xef" * 1024)


def _corrupt_store(path: str) -> str:
    store = IntentStore(path)
    try:
        with store.conn:
            store.conn.executemany(
                "INSERT INTO events "
                "(event_id, workspace_id, device_id, timestamp, event_type, payload) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                [
                    (
                        f"e{i}",
                        "local",
                        "local",
                        "2026-01-01T00:00:00",
                        "JOB_CREATED",
                        f'{{"id": "j{i}", "name": "Job {i}"}}',
                    )
                    for i in range(2_000)
                ],
            )
    finally:
        store.close()
    _corrupt_page(path)
    return path


@pytest.fixture
def corrupt_store(tmp_path, monkeypatch: pytest.MonkeyPatch) -> str:
    db_path = str(tmp_path / "odi.db")
    _corrupt_store(db_path)
    monkeypatch.setenv("AGENTIC_ODI_DB", db_path)
    return db_path


# -- the boot gate ---------------------------------------------------------


def test_a_corrupt_store_answers_with_a_structured_failure(corrupt_store) -> None:
    app = create_app(backend="local")
    with TestClient(app) as client:
        response = client.get("/api/canvas")

    assert response.status_code == 503
    error = response.json()["error"]
    assert error["code"] == "store_corrupt"
    assert corrupt_store in error["message"]
    assert error["suggestion"]
    # A person can act on the message: it never leaks a traceback.
    assert "Traceback" not in response.text


def test_the_boot_failure_names_the_last_backup(corrupt_store, tmp_path, monkeypatch) -> None:
    backups = tmp_path / "backups"
    backups.mkdir()
    (backups / "odi-20260102T061400Z.db").write_bytes(b"good")
    monkeypatch.setenv("AGENTIC_ODI_BACKUP_DIR", str(backups))

    app = create_app(backend="local")
    with TestClient(app) as client:
        response = client.get("/api/canvas")

    error = response.json()["error"]
    assert "06:14" in error["message"]
    assert "odi-20260102T061400Z.db" in error["message"]
    assert "odi-20260102T061400Z.db" in error["suggestion"]


def test_a_corrupt_store_does_not_touch_the_file(corrupt_store) -> None:
    before = os.stat(corrupt_store)
    with open(corrupt_store, "rb") as handle:
        original = handle.read()

    app = create_app(backend="local")
    with TestClient(app) as client:
        client.get("/api/canvas")

    after = os.stat(corrupt_store)
    with open(corrupt_store, "rb") as handle:
        assert handle.read() == original
    assert (after.st_size, after.st_mtime_ns) == (before.st_size, before.st_mtime_ns)


def test_health_and_diagnostics_stay_reachable_on_a_corrupt_store(corrupt_store) -> None:
    """The failure page needs a way to say what is wrong; keep them open."""
    app = create_app(backend="local")
    with TestClient(app) as client:
        health = client.get("/health")
        diagnostics = client.get("/api/diagnostics")

    assert health.status_code == 200
    assert health.json() == {"status": "degraded", "reason": "store_corrupt"}
    assert diagnostics.status_code == 200
    assert diagnostics.json()["db"]["integrity"] == "corrupt"


def test_a_healthy_store_boots_and_reports_ok(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "odi.db")
    IntentStore(db_path).close()
    monkeypatch.setenv("AGENTIC_ODI_DB", db_path)

    app = create_app(backend="local")
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}
        assert client.get("/api/diagnostics").json()["db"]["integrity"] == "ok"


# -- clean shutdown --------------------------------------------------------


def test_a_clean_shutdown_checkpoints_and_closes_both_stores(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "odi.db")
    IntentStore(db_path).close()
    monkeypatch.setenv("AGENTIC_ODI_DB", db_path)

    app = create_app(backend="local")
    with TestClient(app) as client:
        client.post("/api/jobs", json={"name": "Onboard", "description": "d"})
        assert os.path.exists(db_path + "-wal")

    # Leaving the context manager is the shutdown path uvicorn runs on SIGTERM.
    assert not os.path.exists(db_path + "-wal")
    assert not os.path.exists(db_path + "-shm")
    # The conversation memory is closed too.
    memory = app.state.memory
    assert memory._closed is True


def test_a_clean_shutdown_leaves_no_growing_wal(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "odi.db")
    IntentStore(db_path).close()
    monkeypatch.setenv("AGENTIC_ODI_DB", db_path)
    wal_path = db_path + "-wal"

    app = create_app(backend="local")
    with TestClient(app) as client:
        client.post("/api/jobs", json={"name": "Onboard", "description": "d"})

    assert not os.path.exists(wal_path)

    # A second clean cycle is just as clean: no log survives the first stop.
    app2 = create_app(backend="local")
    with TestClient(app2) as client:
        client.get("/api/canvas")
    assert not os.path.exists(wal_path)


def test_shutdown_closes_a_memory_store_without_error(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AGENTIC_ODI_STUDIO_DB", ":memory:")
    memory = StudioMemory(":memory:")
    app = create_app(backend="local", memory=memory)

    with TestClient(app):
        pass

    assert memory._closed is True
    memory.close()  # idempotent


def test_the_store_is_closed_even_when_the_app_never_served_a_request(
    tmp_path, monkeypatch
) -> None:
    db_path = str(tmp_path / "odi.db")
    IntentStore(db_path).close()
    monkeypatch.setenv("AGENTIC_ODI_DB", db_path)

    app = create_app(backend="local")
    with TestClient(app):
        pass

    assert not os.path.exists(db_path + "-wal")


# -- checkpoint policy -----------------------------------------------------


def test_checkpoint_seconds_reads_the_environment(monkeypatch) -> None:
    monkeypatch.delenv("AGENTIC_ODI_CHECKPOINT_SECONDS", raising=False)
    assert checkpoint_seconds() == 60.0

    monkeypatch.setenv("AGENTIC_ODI_CHECKPOINT_SECONDS", "5")
    assert checkpoint_seconds() == 5.0

    monkeypatch.setenv("AGENTIC_ODI_CHECKPOINT_SECONDS", "0")
    assert checkpoint_seconds() == 0.0

    # A bad value falls back to the default rather than crashing the sidecar.
    monkeypatch.setenv("AGENTIC_ODI_CHECKPOINT_SECONDS", "soon")
    assert checkpoint_seconds() == 60.0


def test_a_corrupt_memory_store_reports_a_boot_failure(tmp_path, monkeypatch) -> None:
    """The conversation memory is gated too, with its own label."""
    db_path = str(tmp_path / "odi.db")
    IntentStore(db_path).close()
    monkeypatch.setenv("AGENTIC_ODI_DB", db_path)

    memory_path = tmp_path / "studio.db"
    memory = StudioMemory(str(memory_path))
    memory.create_conversation("hello")
    memory.close()
    _corrupt_page(str(memory_path))

    app = create_app(backend="local")
    with TestClient(app) as client:
        response = client.get("/api/canvas")

    error = response.json()["error"]
    assert error["code"] == "store_corrupt"
    assert "Studio memory" in error["message"]


def test_studio_memory_gate_raises_store_corrupt(tmp_path) -> None:
    memory_path = tmp_path / "studio.db"
    memory = StudioMemory(str(memory_path))
    memory.create_conversation("hello")
    memory.close()
    _corrupt_page(str(memory_path))

    with pytest.raises(StoreCorrupt) as raised:
        StudioMemory(str(memory_path))

    assert raised.value.label == "Your Studio memory"
