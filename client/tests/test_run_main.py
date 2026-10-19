"""Tests for the launcher lifecycle: start, poll, and shut down both services."""

from __future__ import annotations

import signal
import subprocess
from pathlib import Path

import pytest

from client import run


class _FakeProcess:
    def __init__(self, poll_results: list[int | None] | None = None, wait_error=None) -> None:
        self._poll_results = list(poll_results) if poll_results is not None else []
        self._wait_error = wait_error
        self.terminated = False
        self.killed = False

    def poll(self) -> int | None:
        return self._poll_results.pop(0) if self._poll_results else None

    def terminate(self) -> None:
        self.terminated = True

    def wait(self, timeout=None) -> int:
        if self._wait_error is not None:
            raise self._wait_error
        return 0

    def kill(self) -> None:
        self.killed = True


def _quiet_main(monkeypatch) -> None:
    monkeypatch.setattr(run, "is_port_in_use", lambda port: False)
    monkeypatch.setattr(run.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(run.signal, "signal", lambda signum, handler: None)


def test_start_server_exits_when_the_port_is_busy(monkeypatch, capsys) -> None:
    monkeypatch.setattr(run, "is_port_in_use", lambda port: True)

    with pytest.raises(SystemExit) as exc_info:
        run.start_server()

    assert exc_info.value.code == 1
    assert f"Port {run.MCP_PORT} is already in use" in capsys.readouterr().out


def test_start_server_launches_the_fixed_module(monkeypatch, capsys) -> None:
    launched: list[list[str]] = []

    def _popen(argv: list[str]) -> _FakeProcess:
        launched.append(argv)
        return _FakeProcess()

    monkeypatch.setattr(run, "is_port_in_use", lambda port: False)
    monkeypatch.setattr(run.subprocess, "Popen", _popen)

    process = run.start_server()

    assert isinstance(process, _FakeProcess)
    assert launched == [[run.sys.executable, "-m", "mcp_server"]]
    assert "Starting MCP server" in capsys.readouterr().out


def test_start_studio_warns_but_still_launches(monkeypatch, capsys) -> None:
    launched: list[list[str]] = []

    def _popen(argv: list[str]) -> _FakeProcess:
        launched.append(argv)
        return _FakeProcess()

    monkeypatch.setattr(run, "is_port_in_use", lambda port: True)
    monkeypatch.setattr(run.subprocess, "Popen", _popen)

    run.start_studio()

    output = capsys.readouterr().out
    assert f"Port {run.STUDIO_PORT} is already in use" in output
    assert launched == [run.build_commands()[1]]


@pytest.mark.parametrize("exiting", ["server", "studio"])
def test_main_reports_an_unexpected_exit_and_stops_both(monkeypatch, capsys, exiting) -> None:
    _quiet_main(monkeypatch)
    server = _FakeProcess([0] if exiting == "server" else [None])
    studio = _FakeProcess([0] if exiting == "studio" else [None])
    monkeypatch.setattr(run, "start_server", lambda: server)
    monkeypatch.setattr(run, "start_studio", lambda: studio)
    monkeypatch.setattr(run, "SPA_DIST", Path("/nonexistent/studio/dist"))

    with pytest.raises(SystemExit) as exc_info:
        run.main()

    output = capsys.readouterr().out
    expected = (
        "Server exited unexpectedly"
        if exiting == "server"
        else "Studio sidecar exited unexpectedly"
    )
    assert exc_info.value.code == 0
    assert expected in output
    assert "All processes stopped." in output
    assert "Frontend not built" in output
    assert server.terminated is True
    assert studio.terminated is True


def test_main_waits_while_both_processes_are_running(monkeypatch) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr(run, "is_port_in_use", lambda port: False)
    monkeypatch.setattr(run.time, "sleep", sleeps.append)
    monkeypatch.setattr(run.signal, "signal", lambda signum, handler: None)
    monkeypatch.setattr(run, "start_server", lambda: _FakeProcess([None, 0]))
    monkeypatch.setattr(run, "start_studio", lambda: _FakeProcess([None, None]))
    monkeypatch.setattr(run, "SPA_DIST", Path("/nonexistent/studio/dist"))

    with pytest.raises(SystemExit):
        run.main()

    assert sleeps == [2, 1]


def test_main_kills_processes_that_ignore_termination(monkeypatch, capsys) -> None:
    _quiet_main(monkeypatch)
    timeout = subprocess.TimeoutExpired(cmd="odi", timeout=5)
    server = _FakeProcess([0], wait_error=timeout)
    studio = _FakeProcess([None], wait_error=timeout)
    monkeypatch.setattr(run, "start_server", lambda: server)
    monkeypatch.setattr(run, "start_studio", lambda: studio)
    monkeypatch.setattr(run, "SPA_DIST", Path("/nonexistent/studio/dist"))

    with pytest.raises(SystemExit):
        run.main()

    assert server.killed is True
    assert studio.killed is True


def test_main_reports_startup_errors(monkeypatch, capsys) -> None:
    _quiet_main(monkeypatch)

    def _boom() -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(run, "start_server", _boom)

    with pytest.raises(SystemExit):
        run.main()

    output = capsys.readouterr().out
    assert "Error: boom" in output
    assert "All processes stopped." in output


def test_main_installs_signal_handlers(monkeypatch) -> None:
    seen: list[int] = []
    monkeypatch.setattr(run, "is_port_in_use", lambda port: False)
    monkeypatch.setattr(run.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(run.signal, "signal", lambda signum, handler: seen.append(signum))
    monkeypatch.setattr(run, "start_server", lambda: _FakeProcess([0]))
    monkeypatch.setattr(run, "start_studio", lambda: _FakeProcess([None]))
    monkeypatch.setattr(run, "SPA_DIST", Path("/nonexistent/studio/dist"))

    with pytest.raises(SystemExit):
        run.main()

    assert seen == [signal.SIGINT, signal.SIGTERM]
