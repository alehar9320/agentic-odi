"""The ninety-second tour is generated, executed, and stays current.

The tour is a scripted walkthrough, not a recording: every command in
``docs/tour/script.md`` is executed by ``scripts/tour.py``, and the committed
cast and transcript must match a fresh run. A command removed from the product
fails the tour build; a hand-edited cast fails this test.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOUR_PY = ROOT / "scripts" / "tour.py"


def _load_tour():
    spec = importlib.util.spec_from_file_location("tour", TOUR_PY)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["tour"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def tour():
    return _load_tour()


def test_the_tour_completes_within_the_ninety_second_budget(tour) -> None:
    _cast, _readme, seconds = tour.build()
    assert seconds < tour.BUDGET_SECONDS


def test_every_documented_step_runs(tour) -> None:
    # build() executes every step in script.md; a step that cannot run raises.
    _cast, _readme, _seconds = tour.build()
    assert tour.read_steps(), "the tour documents no steps"


def test_committed_artifacts_match_a_fresh_run(tour) -> None:
    cast, readme, _seconds = tour.build()
    assert tour.CAST_PATH.read_text(encoding="utf-8") == cast, (
        "docs/tour/tour.cast is stale; run `uv run python scripts/tour.py`"
    )
    assert tour.README_PATH.read_text(encoding="utf-8") == readme, (
        "docs/tour/README.md is stale; run `uv run python scripts/tour.py`"
    )


def test_a_missing_command_fails_the_tour(tour, monkeypatch, tmp_path) -> None:
    """A command that is not in the product must fail, naming the step."""
    script = tmp_path / "script.md"
    script.write_text(
        "1. `agentic-odi definitely-not-a-command` — a step that cannot run.\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(tour, "SCRIPT_MD", script)
    with pytest.raises(tour.TourError):
        tour.run_tour()
