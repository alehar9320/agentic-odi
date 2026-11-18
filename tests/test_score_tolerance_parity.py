"""The score-mismatch tolerance is one number, not two.

`packages/core` keeps opportunity scores to one decimal place
(`OPPORTUNITY_SCORE_DECIMALS`), and the Studio treats a stored score as matching
its inputs when it is within `SCORE_MISMATCH_TOLERANCE` of the recomputed value.
Nothing connected the two, so core's precision and the Studio's tolerance could
drift apart while every test in each language kept passing.

The Studio has no pytest-visible behaviour, so its half is read from source —
the same approach `test_underserved_threshold_parity.py` takes.
"""

from __future__ import annotations

import re
from pathlib import Path

from agentic_odi_core.models import OPPORTUNITY_SCORE_DECIMALS

ODI_TS = Path(__file__).resolve().parents[1] / "apps/studio/src/lib/odi.ts"
_TOLERANCE = re.compile(r"^export const SCORE_MISMATCH_TOLERANCE = ([0-9.]+);", re.MULTILINE)


def _studio_tolerance() -> float:
    match = _TOLERANCE.search(ODI_TS.read_text(encoding="utf-8"))
    assert match is not None, f"{ODI_TS} does not export SCORE_MISMATCH_TOLERANCE"
    return float(match.group(1))


def test_tolerance_matches_cores_score_decimals() -> None:
    assert _studio_tolerance() == 0.5 * 10**-OPPORTUNITY_SCORE_DECIMALS
