"""Present the alternatives inventory to a reader (M2-07.2).

The inventory itself is recorded in :mod:`agentic_odi_core.models`; this module
turns it into the lines a reader sees — the brief's *Underserved outcomes* entry
and the Studio row. It is a **pure** function of its inputs: no repository
access, so the CLI, the Studio and the brief cannot drift.

Two facts must never be conflated. An outcome whose inventory was recorded and
holds only ``kind='nothing'`` says the customer uses nothing today; an outcome
with no link at all says **not yet inventoried**. Rendering the second as "no
solution" is exactly the fabrication this feature exists to prevent, so the
wording comes from the one map in :data:`~agentic_odi_core.models.EXISTING_SOLUTION_LABELS`
and the no-link case never claims a solution state.

Multiple linked alternatives are multiple customer observations, not a ranking:
the lines keep their input order and never pick a winner. There is no approved
primary-selection field, so none is invented.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from agentic_odi_core.models import EXISTING_SOLUTION_LABELS

#: The one line an un-inventoried outcome renders. It says the unknown plainly
#: and is deliberately distinct from the ``no_linked_nothing`` wording.
NOT_YET_INVENTORIED = EXISTING_SOLUTION_LABELS["no_link_at_all"]


def _escape(text: str) -> str:
    """Escape HTML-significant characters in customer-supplied text.

    Names and notes are text, not markup: a ``<script>`` inside a note must
    render as characters in both the UI and the Markdown brief.
    """
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


@dataclass(frozen=True)
class AlternativeObservation:
    """One recorded alternative as a reader must see it.

    ``adequacy`` is the customer's own rating and is required on a link; it is
    never inferred from the opportunity score. ``usage_n`` is ``None`` when the
    count was not recorded, and renders as unknown rather than zero.
    """

    name: str
    kind: str
    adequacy: float
    usage_n: int | None = None
    note: str | None = None

    @property
    def is_nothing(self) -> bool:
        """Whether this observation is the ``nothing`` row."""
        return self.kind == "nothing"


def format_alternative_line(observation: AlternativeObservation) -> str:
    """One Markdown bullet for a recorded alternative, with its adequacy.

    The adequacy is printed as recorded; the usage count appears only when it
    was recorded, so an unknown count is silent rather than a fabricated zero.
    """
    line = f"- {_escape(observation.name)} ({observation.kind}, adequacy {observation.adequacy:g})"
    if observation.usage_n is not None:
        line += f", n={observation.usage_n}"
    if observation.note:
        line += f" — {_escape(observation.note)}"
    return line


def render_alternative_lines(observations: Sequence[AlternativeObservation]) -> list[str]:
    """The lines for one outcome's recorded alternatives, in input order.

    An empty sequence is the un-inventoried case and renders the one-line
    ``not yet inventoried`` note — never a solution claim and never a zero. A
    non-empty sequence renders one line per observation; the ``nothing`` row is
    shown like any other, because it is evidence, not an absence.
    """
    if not observations:
        return [f"_{NOT_YET_INVENTORIED}_"]
    return [format_alternative_line(observation) for observation in observations]


def solution_label(state: str) -> str:
    """The one sentence for a three-state solution result, or a plain fallback.

    Unknown states are refused loudly rather than defaulting to a solution
    claim, so a new state cannot be silently read as ``yes``.
    """
    try:
        return EXISTING_SOLUTION_LABELS[state]
    except KeyError:
        raise ValueError(f"unknown existing-solution state {state!r}") from None
