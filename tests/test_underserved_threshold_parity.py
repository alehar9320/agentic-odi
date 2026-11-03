"""The boundary between "served" and "underserved" is one number, not two.

`packages/core` buckets a score with `UNDERSERVED_SCORE` and the Studio compares
it with `UNDERSERVED_THRESHOLD` in `apps/studio/src/lib/odi.ts`. Nothing connected
the two, so they could drift apart while every test in each language kept passing
and a user read "underserved" in the table and "served" in the pill.

The Studio has no pytest-visible behaviour, so its half is read from source — the
same approach `test_worker_error_shape.py` takes for the Cloudflare Worker.
"""

from __future__ import annotations

import re
from pathlib import Path

from agentic_odi_core.evaluation import UNDERSERVED_SCORE, classify_opportunity

ODI_TS = Path(__file__).resolve().parents[1] / "apps/studio/src/lib/odi.ts"
_THRESHOLD = re.compile(r"^export const UNDERSERVED_THRESHOLD = ([0-9.]+);", re.MULTILINE)


def _studio_threshold() -> float:
    match = _THRESHOLD.search(ODI_TS.read_text(encoding="utf-8"))
    assert match is not None, f"{ODI_TS} does not export UNDERSERVED_THRESHOLD"
    return float(match.group(1))


def test_both_languages_draw_the_line_at_the_same_number() -> None:
    assert _studio_threshold() == UNDERSERVED_SCORE


def test_the_core_side_is_strictly_greater_than_the_line() -> None:
    assert classify_opportunity(UNDERSERVED_SCORE) == "appropriate"
    assert classify_opportunity(UNDERSERVED_SCORE + 0.1) == "underserved"
