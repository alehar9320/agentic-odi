"""Tests for first-run onboarding signal extraction and gating."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from agentic_odi_cli import onboard, profile


class _Response:
    def __init__(self, text: str, url: str = "https://acme.test/product") -> None:
        self.text = text
        self.url = url

    def raise_for_status(self) -> None:
        return None


def test_page_signals_repr_summarises_the_fetch() -> None:
    signals = onboard.PageSignals(
        title="Acme",
        meta_description="desc",
        domain="acme.test",
        primary_user=None,
        business_model=None,
        core_problem=None,
        current_focus=None,
        confidence=0.9,
    )

    assert signals.title == "Acme"
    assert "Acme" in repr(signals)
    assert "acme.test" in repr(signals)


def test_infer_baseline_marks_keyword_rich_pages_high_confidence() -> None:
    signals = onboard.PageSignals(
        title="DevTools error tracking and monitoring",
        meta_description="performance analytics",
        domain="acme.test",
    )

    baseline, scores = onboard.infer_baseline(signals)

    assert baseline.source == "url"
    assert baseline.domain == "acme.test"
    assert baseline.inferred is True
    assert baseline.confidence is not None and baseline.confidence > 0.5
    assert scores["devtools"] == 3
    assert scores["error"] == 2


def test_infer_baseline_marks_keyword_poor_pages_low_confidence() -> None:
    signals = onboard.PageSignals(
        title="Acme",
        meta_description="A friendly product",
        domain=None,
    )

    baseline, scores = onboard.infer_baseline(signals)

    assert baseline.domain == ""
    assert baseline.confidence is not None and baseline.confidence < 0.5
    assert scores == {}


def test_extract_signals_reads_title_meta_and_domain() -> None:
    html = (
        "<html><head><title>Acme DevTools</title>"
        '<meta name="description" content="Error tracking for teams">'
        "</head></html>"
    )

    signals = onboard._extract_signals(html, "https://acme.test/product")

    assert signals.title == "Acme DevTools"
    assert signals.meta_description == "Error tracking for teams"
    assert signals.domain == "acme.test"
    assert signals.confidence == 0.0


def test_extract_signals_defaults_missing_metadata_to_empty() -> None:
    signals = onboard._extract_signals("<html></html>", "https://acme.test")

    assert signals.title == ""
    assert signals.meta_description == ""
    assert signals.confidence == 0.0


def test_fetch_signals_returns_a_baseline_for_reachable_pages(monkeypatch) -> None:
    html = "<html><head><title>DevTools error tracking</title></head></html>"
    monkeypatch.setattr(onboard.httpx, "get", lambda *args, **kwargs: _Response(html))

    baseline, low_confidence = onboard.fetch_signals("https://acme.test")

    assert baseline.domain == "acme.test"
    assert baseline.confidence is not None and baseline.confidence > 0.5
    assert low_confidence is False


def test_fetch_signals_falls_back_to_typed_path_on_fetch_errors(monkeypatch) -> None:
    def _boom(*args, **kwargs):
        raise RuntimeError("offline")

    monkeypatch.setattr(onboard.httpx, "get", _boom)

    signals, low_confidence = onboard.fetch_signals("https://acme.test")

    assert isinstance(signals, onboard.PageSignals)
    assert signals.title == ""
    assert signals.confidence is not None and signals.confidence < 0.5
    assert low_confidence is True


def test_fetch_signals_falls_back_when_the_status_is_an_error(monkeypatch) -> None:
    class _ErrorResponse(_Response):
        def raise_for_status(self) -> None:
            raise RuntimeError("500")

    monkeypatch.setattr(onboard.httpx, "get", lambda *args, **kwargs: _ErrorResponse("ignored"))

    signals, low_confidence = onboard.fetch_signals("https://acme.test")

    assert isinstance(signals, onboard.PageSignals)
    assert signals.title == ""
    assert low_confidence is True


def test_contract_copy_is_available() -> None:
    assert any("consent" in line for line in onboard.HONESTY_CONTRACT_LINES)
    assert any("Product" in line for line in onboard.CARD_LINES)


def _interactive(monkeypatch) -> None:
    monkeypatch.setattr(onboard.sys, "stdin", SimpleNamespace(isatty=lambda: True))
    monkeypatch.setattr(onboard.sys, "stdout", SimpleNamespace(isatty=lambda: True))


def test_maybe_run_first_launch_skips_when_no_onboard(monkeypatch, capsys) -> None:
    _interactive(monkeypatch)

    onboard.maybe_run_first_launch(no_onboard=True)

    assert capsys.readouterr().out == ""


def test_maybe_run_first_launch_skips_when_a_baseline_exists(monkeypatch, capsys) -> None:
    _interactive(monkeypatch)
    monkeypatch.setattr(profile, "baseline_exists", lambda: True)

    onboard.maybe_run_first_launch()

    assert capsys.readouterr().out == ""


def test_maybe_run_first_launch_skips_without_a_tty(monkeypatch, capsys) -> None:
    monkeypatch.setattr(onboard.sys, "stdin", SimpleNamespace(isatty=lambda: False))
    monkeypatch.setattr(onboard.sys, "stdout", SimpleNamespace(isatty=lambda: True))
    monkeypatch.setattr(profile, "baseline_exists", lambda: False)

    onboard.maybe_run_first_launch()

    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("subcommand", ["setup", "profile", "version", "help"])
def test_maybe_run_first_launch_skips_management_subcommands(
    monkeypatch, capsys, subcommand
) -> None:
    _interactive(monkeypatch)
    monkeypatch.setattr(profile, "baseline_exists", lambda: False)

    onboard.maybe_run_first_launch(invoked_subcommand=subcommand)

    assert capsys.readouterr().out == ""


def test_maybe_run_first_launch_shows_the_card(monkeypatch) -> None:
    _interactive(monkeypatch)
    monkeypatch.setattr(profile, "baseline_exists", lambda: False)
    printed: list[str] = []
    monkeypatch.setattr(onboard.typer, "echo", printed.append)

    onboard.maybe_run_first_launch()

    output = "".join(printed)
    assert "First-run onboarding card" in output
    assert "consent" in output
