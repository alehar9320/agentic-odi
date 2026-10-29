"""The Odi banner: shape, colour, and when it is allowed to appear."""

from __future__ import annotations

from agentic_odi_cli import mascot


class _Stream:
    """A stand-in for a terminal with a known encoding."""

    def __init__(self, tty: bool, encoding: str) -> None:
        self._tty = tty
        self._encoding = encoding

    @property
    def encoding(self) -> str:
        return self._encoding

    def isatty(self) -> bool:
        return self._tty


def _NotATty() -> _Stream:
    return _Stream(tty=False, encoding="utf-8")


def _Tty() -> _Stream:
    return _Stream(tty=True, encoding="utf-8")


def _Latin1() -> _Stream:
    return _Stream(tty=True, encoding="latin-1")


def test_banner_has_sixteen_rows_of_at_most_thirty_two_columns():
    lines = mascot.MASCOT_ASCII.splitlines()
    assert len(lines) == 16
    assert all(len(line) <= 32 for line in lines)
    assert max(len(line) for line in lines) > 20


def test_banner_is_not_empty_and_contains_the_otter():
    assert "▀" in mascot.MASCOT_ASCII
    assert "█" in mascot.MASCOT_ASCII


def test_ansi_banner_uses_24_bit_colour():
    assert "\x1b[38;2;" in mascot.MASCOT_ANSI
    assert "\x1b[48;2;" in mascot.MASCOT_ANSI
    assert "\x1b[0m" in mascot.MASCOT_ANSI


def test_banner_is_hidden_from_a_pipe():
    assert mascot.should_show_banner(_NotATty()) is False


def test_banner_is_shown_on_a_tty(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    assert mascot.should_show_banner(_Tty()) is True


def test_banner_is_hidden_when_the_terminal_cannot_encode_it(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    assert mascot.should_show_banner(_Latin1()) is False


def test_no_color_keeps_the_banner_but_drops_the_colour(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    assert mascot.should_show_banner(_Tty()) is True
    assert "\x1b[38;2;" not in mascot.render_banner(color=False)


def test_render_banner_switches_between_the_two_forms():
    assert mascot.render_banner(color=True) == mascot.MASCOT_ANSI
    assert mascot.render_banner(color=False) == mascot.MASCOT_ASCII
