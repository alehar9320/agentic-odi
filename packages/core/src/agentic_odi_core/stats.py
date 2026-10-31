"""Deterministic statistics for the trust surfaces (B3).

The percentile bootstrap lives here as a pure function over numeric sequences,
so it can be tested against hand-computed fixtures without a repository. It is
deliberately the only place the interval convention is written down.

Provisional convention (pending the B3 gate; see ``docs/superpowers/plans``):

* Confidence level 0.95, i.e. the 2.5th and 97.5th percentiles.
* 1000 resamples from ``random.Random(seed)`` with ``seed=0`` by default, so
  identical input gives identical bounds across runs and processes.
* Percentiles use linear interpolation between order statistics.
* Importance and satisfaction are resampled with one shared index per draw, so
  the correlation between the two dimensions survives resampling.
* A single observation gets a zero-width band whose ``mid`` is the score; an
  empty sample is refused rather than answered with a fabricated band.

Every one of those choices is a decision the B3 issue says must be approved, so
they are named here in one place and pinned by tests. Changing one changes every
band the product shows, which is exactly why it is not spread across call sites.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from agentic_odi_core.errors import ValidationError
from agentic_odi_core.models import compute_opportunity_score

#: The provisional conventions, named so a caller can see and cite them.
DEFAULT_SAMPLES = 1000
DEFAULT_SEED = 0
DEFAULT_CONFIDENCE_LEVEL = 0.95


@dataclass(frozen=True)
class Interval:
    """A percentile-bootstrap band around an opportunity score.

    ``mid`` is the plug-in estimate (the score of the means), not automatically
    the median of the bootstrap distribution. ``low``/``high`` are the bootstrap
    percentiles, so ``mid`` is not guaranteed to lie inside them; that is a
    property of the approved construction, not a bug to be clipped away.
    """

    low: float
    mid: float
    high: float
    n: int
    confidence_level: float
    samples: int
    seed: int


def percentile(sorted_values: Sequence[float], fraction: float) -> float:
    """Linear-interpolated percentile of an already-sorted sequence.

    Public because the B2 aggregate reports p10/p90 with the same convention the
    band uses, so a spread and a band cannot drift apart.
    """
    if not sorted_values:
        raise ValidationError("cannot take a percentile of an empty sequence")
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    rank = fraction * (len(sorted_values) - 1)
    lower = int(rank)
    upper = min(lower + 1, len(sorted_values) - 1)
    weight = rank - lower
    return float(sorted_values[lower] + (sorted_values[upper] - sorted_values[lower]) * weight)


def _validate_observations(importance: Sequence[float], satisfaction: Sequence[float]) -> None:
    if len(importance) != len(satisfaction):
        raise ValidationError(
            "importance and satisfaction must have the same length; "
            "a band needs one paired observation per respondent"
        )
    for value in (*importance, *satisfaction):
        if (
            not isinstance(value, (int, float))
            or value != value
            or value in (float("inf"), float("-inf"))
        ):
            raise ValidationError(f"observation must be a finite number, got {value!r}")
        if not (1.0 <= value <= 10.0):
            raise ValidationError(f"observation must be between 1 and 10, got {value!r}")


def opportunity_interval(
    importance: Sequence[float],
    satisfaction: Sequence[float],
    *,
    samples: int = DEFAULT_SAMPLES,
    seed: int = DEFAULT_SEED,
    confidence_level: float = DEFAULT_CONFIDENCE_LEVEL,
) -> Interval:
    """The percentile-bootstrap band for a set of paired observations.

    Resamples respondent indices with replacement (one shared index per draw, so
    the importance/satisfaction pairing is preserved) and recomputes the
    opportunity score through :func:`compute_opportunity_score` on each
    resample's means. Deterministic for a given ``seed`` and input.
    """
    import random

    importance = list(importance)
    satisfaction = list(satisfaction)
    _validate_observations(importance, satisfaction)
    n = len(importance)
    if n == 0:
        raise ValidationError(
            "an interval needs at least one observation; "
            "an outcome with no sample has no band, not a zero-width one"
        )
    if samples < 1:
        raise ValidationError(f"samples must be at least 1, got {samples}")
    if not (0.0 < confidence_level < 1.0):
        raise ValidationError(f"confidence_level must be between 0 and 1, got {confidence_level}")

    mean_importance = sum(importance) / n
    mean_satisfaction = sum(satisfaction) / n
    mid = compute_opportunity_score(mean_importance, mean_satisfaction)

    if n == 1:
        return Interval(
            low=mid,
            mid=mid,
            high=mid,
            n=1,
            confidence_level=confidence_level,
            samples=samples,
            seed=seed,
        )

    rng = random.Random(seed)
    scores: list[float] = []
    for _ in range(samples):
        imp_total = 0.0
        sat_total = 0.0
        for _ in range(n):
            index = rng.randrange(n)
            imp_total += importance[index]
            sat_total += satisfaction[index]
        scores.append(compute_opportunity_score(imp_total / n, sat_total / n))
    scores.sort()

    tail = (1.0 - confidence_level) / 2.0
    low = percentile(scores, tail)
    high = percentile(scores, 1.0 - tail)
    return Interval(
        low=low,
        mid=mid,
        high=high,
        n=n,
        confidence_level=confidence_level,
        samples=samples,
        seed=seed,
    )
