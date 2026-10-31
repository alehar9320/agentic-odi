"""Foreground daemon: one instance, one ticker, one heartbeat file."""

from __future__ import annotations

import os
import signal
import time
from pathlib import Path
from types import FrameType
from typing import Any

from agentic_odi_integrations_openhands import config
from agentic_odi_integrations_openhands.service import (
    OrchestratorService,
    TickReport,
    sleep_until_next,
    write_heartbeat,
)


class AlreadyRunning(RuntimeError):
    pass


class DaemonLock:
    """An ``O_CREAT|O_EXCL`` lock with stale-PID recovery."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or config.lock_path()
        self._held = False

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        for _ in range(2):
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            except FileExistsError:
                if self._stale():
                    try:
                        self.path.unlink()
                    except FileNotFoundError:
                        pass
                    continue
                pid = self._read_pid()
                raise AlreadyRunning(
                    f"another orchestrator daemon is running (pid {pid or 'unknown'}); "
                    f"stop it or remove {self.path}"
                ) from None
            with os.fdopen(fd, "w") as handle:
                handle.write(str(os.getpid()))
            self._held = True
            return
        raise AlreadyRunning(f"could not acquire {self.path}")

    def _read_pid(self) -> int | None:
        try:
            return int(self.path.read_text().strip())
        except (OSError, ValueError):
            return None

    def _stale(self) -> bool:
        pid = self._read_pid()
        if pid is None:
            return True
        try:
            os.kill(pid, 0)
        except OSError:
            return True
        return False

    def release(self) -> None:
        if not self._held:
            return
        try:
            if self._read_pid() == os.getpid():
                self.path.unlink()
        except OSError:
            pass
        self._held = False


class OrchestratorDaemon:
    def __init__(
        self,
        service: OrchestratorService,
        *,
        interval_s: int | None = None,
        once: bool = False,
        lock: DaemonLock | None = None,
        heartbeat_path: Path | None = None,
        on_tick: Any | None = None,
    ) -> None:
        self.service = service
        self.interval_s = interval_s or service.settings.poll_interval_s
        self.once = once
        self.lock = lock or DaemonLock()
        self.heartbeat_path = heartbeat_path or config.heartbeat_path(service.settings)
        self._stop = False
        self._received_stop = False
        self.on_tick = on_tick

    def request_stop(self, _signum: int | None = None, _frame: FrameType | None = None) -> None:
        self._stop = True
        self._received_stop = True

    @property
    def received_stop(self) -> bool:
        return self._received_stop

    def run(self) -> TickReport | None:
        self.lock.acquire()
        previous = self._install_signal_handlers()
        try:
            notes = self.service.recover()
            if notes:
                for note in notes:
                    print(f"recover: {note}", flush=True)
            if self.once:
                report = self._tick()
                return report
            while not self._stop:
                self._tick()
                sleep_until_next(self.interval_s, lambda: self._stop)
            return None
        finally:
            self._restore_signal_handlers(previous)
            self.lock.release()

    def _tick(self) -> TickReport:
        report = self.service.tick()
        counts = self.service.store.counts()
        write_heartbeat(
            self.heartbeat_path,
            {
                "interval_s": self.interval_s,
                "counts": counts,
                "last_report": {
                    "enqueued_schedules": report.enqueued_schedules,
                    "dispatched": report.dispatched,
                    "supervised": report.supervised,
                    "terminal": report.terminal,
                },
            },
        )
        if self.on_tick is not None:
            self.on_tick(report)
        return report

    def _install_signal_handlers(self) -> dict[int, Any]:
        previous: dict[int, Any] = {}
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                previous[sig] = signal.signal(sig, self.request_stop)
            except (ValueError, OSError):  # pragma: no cover - non-main thread
                continue
        return previous

    def _restore_signal_handlers(self, previous: dict[int, Any]) -> None:
        for sig, handler in previous.items():
            try:
                signal.signal(sig, handler)
            except (ValueError, OSError):  # pragma: no cover
                continue


def sleep_for(seconds: float) -> None:
    time.sleep(max(seconds, 0))
