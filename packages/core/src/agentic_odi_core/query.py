"""Shared outcome search for the whole library (ALH-194 / parent ALH-66).

``OutcomeQuery`` is a plain dataclass with no store access so that every
consumer — the CLI, the API, later bulk edit and saved views — describes the
same narrowing.  :func:`search_outcomes` runs it against any repository and is
read-only: filtering happens here, in the store, not over a fully loaded list
in a client.

Decisions settled from the parent's readiness blocker:

* Multi-value fields (``theme_ids``, ``tags``) are one dimension with OR
  semantics; an outcome in either theme appears once. Different dimensions
  combine with AND.
* Permitted sorts are exactly :data:`OUTCOME_SORTS` — the library is narrowed
  with the same ordering the paginated list reads use.
* The score band is inclusive at both ends and excludes unscored outcomes;
  a missing score is not evidence of a low one.
* Confidence vocabulary: ``"scored"`` means both importance and satisfaction
  were recorded, ``"unscored"`` means either is missing. It names whether a
  score exists, never what it says.
* Facet counts follow the dimension-removed rule, so buckets overlap by
  design and are not forced to add up to the total.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from agentic_odi_core.errors import ValidationError
from agentic_odi_core.models import JobStage, Outcome, is_scored
from agentic_odi_core.repository import OUTCOME_SORTS, Repository, page, sort_outcomes
from agentic_odi_core.theme_tree import subtree_ids

CONFIDENCE_LEVELS = ("scored", "unscored")


@dataclass
class OutcomeQuery:
    """How to narrow the outcome library. Every field is optional."""

    text: str | None = None
    stage: str | None = None
    theme_ids: list[str] = field(default_factory=list)
    confidence: str | None = None
    tags: list[str] = field(default_factory=list)
    min_score: float | None = None
    max_score: float | None = None
    job_id: str | None = None
    sort: str = "opportunity_score"
    include_children: bool = False


def _validate_query(repo: Repository, query: OutcomeQuery) -> None:
    if query.stage is not None and query.stage not in {stage.value for stage in JobStage}:
        raise ValidationError(f"Unknown stage: {query.stage}")
    if query.confidence is not None and query.confidence not in CONFIDENCE_LEVELS:
        raise ValidationError(
            f"Unknown confidence: {query.confidence}. Use one of: {', '.join(CONFIDENCE_LEVELS)}"
        )
    if query.sort not in OUTCOME_SORTS:
        raise ValidationError(f"Unknown sort: {query.sort}. Use one of: {', '.join(OUTCOME_SORTS)}")
    for theme_id in query.theme_ids:
        if repo.get_theme(theme_id) is None:
            raise ValidationError(f"Unknown theme: {theme_id}")


def _matches_text(outcome: Outcome, needle: str, repo: Repository) -> bool:
    if needle in outcome.statement.lower():
        return True
    if any(
        needle in repo.themes[tid].name.lower() for tid in outcome.theme_ids if tid in repo.themes
    ):
        return True
    return any(
        evidence.outcome_id == outcome.id and needle in evidence.content.lower()
        for evidence in repo.evidence.values()
    )


def _matches_stage(outcome: Outcome, stage: str, repo: Repository) -> bool:
    if outcome.step_id is None:
        return False
    step = repo.get_step(outcome.step_id)
    return step is not None and step.stage is not None and step.stage.value == stage


def _passes(
    outcome: Outcome, repo: Repository, query: OutcomeQuery, skip: str | None = None
) -> bool:
    if skip != "stage" and query.stage is not None:
        if not _matches_stage(outcome, query.stage, repo):
            return False
    if skip != "theme" and query.theme_ids:
        if not any(tid in query.theme_ids for tid in outcome.theme_ids):
            return False
    if query.tags:
        if not any(tag in query.tags for tag in outcome.tags):
            return False
    if skip != "confidence" and query.confidence is not None:
        if (query.confidence == "scored") != is_scored(outcome):
            return False
    if query.min_score is not None and (
        outcome.opportunity_score is None or outcome.opportunity_score < query.min_score
    ):
        return False
    if query.max_score is not None and (
        outcome.opportunity_score is None or outcome.opportunity_score > query.max_score
    ):
        return False
    if query.text is not None and not _matches_text(outcome, query.text.lower(), repo):
        return False
    return True


def _facet_counts(candidates: list[Outcome], repo: Repository) -> dict[str, Any]:
    stages: dict[str, int] = {stage.value: 0 for stage in JobStage}
    for outcome in candidates:
        if outcome.step_id is not None:
            step = repo.get_step(outcome.step_id)
            if step is not None and step.stage is not None:
                stages[step.stage.value] += 1
    themes = {theme_id: 0 for theme_id in repo.themes}
    for outcome in candidates:
        for theme_id in outcome.theme_ids:
            if theme_id in themes:
                themes[theme_id] += 1
    confidence = {"scored": 0, "unscored": 0}
    for outcome in candidates:
        confidence["scored" if is_scored(outcome) else "unscored"] += 1
    return {"stage": stages, "theme": themes, "confidence": confidence}


def search_outcomes(
    repo: Repository,
    query: OutcomeQuery,
    limit: int | None = None,
    offset: int = 0,
) -> dict[str, Any]:
    """Return ``{items, total, facets}`` for the query against this store.

    ``items`` are JSON-ready outcome dicts in the requested order; ``total``
    counts them before pagination; ``facets`` holds the counts each filter
    dimension would show with that dimension's own filter removed.
    """
    _validate_query(repo, query)
    if query.include_children and query.theme_ids:
        # A theme can stand for its whole branch, and it does so here rather than in whatever is
        # looking at the list: the rollup walks the same ids, so the count beside a theme and the
        # results under it are the same question answered once.
        branch = {
            theme_id
            for selected in query.theme_ids
            for theme_id in subtree_ids(repo.themes, selected)
        }
        query = replace(
            query, theme_ids=[*query.theme_ids, *(t for t in branch if t not in query.theme_ids)]
        )
    candidates = [
        outcome
        for outcome in repo.outcomes.values()
        if query.job_id is None or outcome.job_id == query.job_id
    ]
    matched = [outcome for outcome in candidates if _passes(outcome, repo, query)]
    facets: dict[str, Any] = {}
    for dimension in ("stage", "theme", "confidence"):
        # Dimension-removed: each row is the same query with only its own
        # filter off, so the facet row can widen or narrow from itself
        # without contradicting the results beside it.
        facets[dimension] = _facet_counts(
            [outcome for outcome in candidates if _passes(outcome, repo, query, skip=dimension)],
            repo,
        )[dimension]
    ordered = sort_outcomes(matched, query.sort)
    return {
        "items": [outcome.model_dump(mode="json") for outcome in page(ordered, limit, offset)],
        "total": len(matched),
        "facets": facets,
    }
