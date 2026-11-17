"""The shared logging configuration is idempotent and level-aware."""

from __future__ import annotations

import logging

import pytest
from agentic_odi_core import logging as odi_logging


@pytest.fixture(autouse=True)
def _reset_logging() -> None:
    """Undo whatever a test configured, so the next test starts clean."""
    root = logging.getLogger()
    before = list(root.handlers)
    odi_logging._configured = False
    yield
    for handler in list(root.handlers):
        if handler not in before:
            root.removeHandler(handler)
    root.setLevel(logging.WARNING)
    odi_logging._configured = False


def test_configure_logging_installs_exactly_one_handler() -> None:
    root = logging.getLogger()
    before = len(root.handlers)

    odi_logging.configure_logging()

    assert len(root.handlers) == before + 1


def test_configure_logging_twice_does_not_duplicate_handlers() -> None:
    root = logging.getLogger()

    odi_logging.configure_logging()
    after_first = len(root.handlers)
    odi_logging.configure_logging()

    assert len(root.handlers) == after_first


def test_configure_logging_honours_the_explicit_level() -> None:
    odi_logging.configure_logging("DEBUG")

    assert logging.getLogger().level == logging.DEBUG


def test_configure_logging_reads_the_level_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(odi_logging.LOG_LEVEL_ENV, "WARNING")

    odi_logging.configure_logging()

    assert logging.getLogger().level == logging.WARNING


def test_configure_logging_defaults_to_info(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(odi_logging.LOG_LEVEL_ENV, raising=False)

    odi_logging.configure_logging()

    assert logging.getLogger().level == logging.INFO


def test_configure_logging_falls_back_on_an_unknown_level() -> None:
    odi_logging.configure_logging("LOUD")

    assert logging.getLogger().level == logging.INFO
