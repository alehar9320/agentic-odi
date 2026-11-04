"""ALH-163 (M2-01.2) — the theme tree read: what a branch holds, and what tops it.

A rollup is a read over memberships that already exist. Nothing here writes, caches or stores a
number: the same store folded twice answers the same thing, which is the only reason the board's
count and the terminal's can be trusted to agree.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from pydantic import BaseModel, Field

from agentic_odi_core.models import THEME_DEPTH, Outcome, Theme
from agentic_odi_core.query import is_scored
from agentic_odi_core.repository import rank_outcomes


class ThemeRollup(BaseModel):
    """One branch of the theme tree, counted once per outcome.

    ``outcomes`` is the union of the theme's own memberships and its children's — an outcome filed
    under a parent and under two children is one outcome, not three. ``measured`` is reported
    apart from it because a theme full of unscored outcomes is not progress. The top is
    **absent** rather than ``0.0`` when nothing in the branch has been scored: a missing score is
    not evidence of low opportunity, and the surfaces that render this all have to say so alike.
    """

    theme_id: str
    name: str
    parent_id: str | None
    outcomes: int = Field(ge=0, description="Outcomes filed under this theme or its children")
    measured: int = Field(ge=0, description="Of those, the ones with both importance and satisfaction")
    top_opportunity: float | None = Field(
        None, description="The best opportunity score in the branch, or None if nothing is scored"
    )
    top_statement: str | None = Field(
        None, description="The statement of that outcome, or None if nothing is scored"
    )

    def as_dict(self) -> dict[str, Any]:
        """The body every door returns: one object, JSON-safe, no invented zeros."""
        return self.model_dump(mode="json")


def subtree_ids(
    themes: Mapping[str, Theme], theme_id: str, depth: int = THEME_DEPTH
) -> list[str]:
    """The theme itself first, then the themes under it, at most ``depth - 1`` levels down.

    ``Theme`` forbids only a theme being its own parent, so a store written before the service's
    two-level check — or replayed from an edited event log — can hold a parent chain that cycles.
    The bound and the visited set are why a corrupt chain returns what it has instead of spinning.
    """
    if theme_id not in themes:
        return []
    children: dict[str, list[str]] = {}
    for theme in themes.values():
        if theme.parent_id is not None:
            children.setdefault(theme.parent_id, []).append(theme.id)

    found = [theme_id]
    visited = {theme_id}
    level = [theme_id]
    for _ in range(max(depth - 1, 0)):
        below = [
            child for parent in level for child in children.get(parent, []) if child not in visited
        ]
        visited.update(below)
        found.extend(below)
        level = below
    return found


def branch_outcomes(
    themes: Mapping[str, Theme], outcomes: Iterable[Outcome], theme_id: str
) -> list[Outcome]:
    """The live outcomes filed anywhere in this branch — each of them once.

    An outcome deleted from the store is simply not in ``outcomes``, so no count ever belongs to a
    theme that only a stale membership mentions.
    """
    branch = set(subtree_ids(themes, theme_id))
    members: dict[str, Outcome] = {}
    for outcome in outcomes:
        if branch.intersection(outcome.theme_ids):
            members[outcome.id] = outcome
    return list(members.values())


def build_rollup(
    theme: Theme, themes: Mapping[str, Theme], outcomes: Iterable[Outcome]
) -> ThemeRollup:
    """Roll one theme up from the models in hand, without a service or a store."""
    members = branch_outcomes(themes, outcomes, theme.id)
    scored = rank_outcomes([outcome for outcome in members if is_scored(outcome)])
    top = scored[0] if scored else None
    return ThemeRollup(
        theme_id=theme.id,
        name=theme.name,
        parent_id=theme.parent_id,
        outcomes=len(members),
        measured=len(scored),
        top_opportunity=None if top is None else top.opportunity_score,
        top_statement=None if top is None else top.statement,
    )


def _sibling_key(theme: Theme) -> tuple[int, str, str]:
    return (theme.ordinal, theme.name.lower(), theme.name)


def tree_order(themes: Iterable[Theme]) -> list[Theme]:
    """Parents before their children, siblings by ``ordinal`` then name.

    The tree is read top-down, so a listing sorted by name alone would bury a child under an
    unrelated parent. A theme whose parent is not in scope — a workspace listing, a job filter —
    stands as a root here rather than vanishing.
    """
    in_scope = {theme.id: theme for theme in themes}
    children: dict[str, list[Theme]] = {}
    roots: list[Theme] = []
    for theme in in_scope.values():
        if theme.parent_id is None or theme.parent_id not in in_scope:
            roots.append(theme)
        else:
            children.setdefault(theme.parent_id, []).append(theme)

    ordered: list[Theme] = []
    for root in sorted(roots, key=_sibling_key):
        ordered.append(root)
        for child in sorted(children.get(root.id, []), key=_sibling_key):
            ordered.append(child)
    return ordered
