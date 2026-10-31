from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import pytest
from agentic_odi_integrations_openhands import (
    AlreadyRunning,
    DaemonLock,
    OrchestratorDaemon,
    OrchestratorSettings,
)
from agentic_odi_integrations_openhands.service import TickReport, _read_heartbeat


class StubService:
    def __init__(self) -> None:
        self.settings = OrchestratorSettings(poll_interval_s=1)
        self.store = type("Store", (), {"counts": lambda self: {"queued": 2}})()
        self.ticks = 0

    def recover(self) -> list[str]:
        return []

    def tick(self) -> TickReport:
        self.ticks += 1
        return TickReport(dispatched=1)


def test_lock_is_exclusive_and_released(tmp_path) -> None:
    path = tmp_path / "daemon.lock"
    first = DaemonLock(path)
    first.acquire()
    assert path.read_text().strip() == str(os.getpid())
    with pytest.raises(AlreadyRunning):
        DaemonLock(path).acquire()
    first.release()
    assert not path.exists()


def test_stale_pid_is_recovered(tmp_path) -> None:
    path = tmp_path / "daemon.lock"
    path.write_text("999999999")
    lock = DaemonLock(path)
    lock.acquire()
    assert path.read_text().strip() == str(os.getpid())
    lock.release()


def test_corrupt_pid_is_treated_as_stale(tmp_path) -> None:
    path = tmp_path / "daemon.lock"
    path.write_text("not-a-pid")
    lock = DaemonLock(path)
    lock.acquire()
    assert path.read_text().strip() == str(os.getpid())
    lock.release()


def test_release_is_a_noop_when_nothing_is_held(tmp_path) -> None:
    path = tmp_path / "daemon.lock"
    DaemonLock(path).release()
    assert not path.exists()


def test_release_leaves_a_lock_owned_by_another_process(tmp_path) -> None:
    path = tmp_path / "daemon.lock"
    lock = DaemonLock(path)
    lock.acquire()
    path.write_text("999999999")
    lock.release()
    assert path.exists()


def test_loop_reports_recovery_and_stops_after_one_tick(tmp_path, capsys) -> None:
    service = StubService()
    service.recover = lambda: ["run-1: adopted conversation"]  # type: ignore[method-assign]
    seen: list[TickReport] = []

    def on_tick(report: TickReport) -> None:
        seen.append(report)
        daemon.request_stop()

    daemon = OrchestratorDaemon(
        service,  # type: ignore[arg-type]
        interval_s=1,
        lock=DaemonLock(tmp_path / "lock"),
        heartbeat_path=tmp_path / "heartbeat.json",
        on_tick=on_tick,
    )

    assert daemon.run() is None
    assert service.ticks == 1
    assert [report.dispatched for report in seen] == [1]
    assert daemon.received_stop is True
    assert "recover: run-1: adopted conversation" in capsys.readouterr().out
    assert not (tmp_path / "lock").exists()


def test_a_missing_heartbeat_means_the_daemon_is_not_running(tmp_path) -> None:
    assert _read_heartbeat(tmp_path / "heartbeat.json", 15) == (None, None, False)


def test_a_corrupt_heartbeat_is_not_a_running_daemon(tmp_path) -> None:
    path = tmp_path / "heartbeat.json"
    path.write_text("{not json")
    assert _read_heartbeat(path, 15) == (None, None, False)


def test_a_live_fresh_pid_is_running(tmp_path) -> None:
    path = tmp_path / "heartbeat.json"
    path.write_text(
        json.dumps({"pid": os.getpid(), "timestamp": datetime.now(timezone.utc).isoformat()})
    )
    stamp, pid, running = _read_heartbeat(path, 15)
    assert stamp is not None
    assert pid == os.getpid()
    assert running is True


def test_a_dead_pid_is_not_running(tmp_path) -> None:
    path = tmp_path / "heartbeat.json"
    path.write_text(
        json.dumps({"pid": 999999999, "timestamp": datetime.now(timezone.utc).isoformat()})
    )
    _, pid, running = _read_heartbeat(path, 15)
    assert pid == 999999999
    assert running is False


def test_once_runs_one_tick_and_writes_heartbeat(tmp_path) -> None:
    service = StubService()
    heartbeat = tmp_path / "heartbeat.json"
    daemon = OrchestratorDaemon(
        service,  # type: ignore[arg-type]
        once=True,
        lock=DaemonLock(tmp_path / "lock"),
        heartbeat_path=heartbeat,
    )

    report = daemon.run()

    assert report is not None and report.dispatched == 1
    assert service.ticks == 1
    payload = json.loads(heartbeat.read_text())
    assert payload["pid"] == os.getpid()
    assert payload["counts"] == {"queued": 2}
    assert payload["last_report"]["dispatched"] == 1
    assert not (tmp_path / "lock").exists()
