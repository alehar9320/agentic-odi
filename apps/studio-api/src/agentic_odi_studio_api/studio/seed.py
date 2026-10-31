"""The prototype canvas, drawn from the demo workspace that ships with the core.

This used to be hand-typed prototype data with keys the model does not have
(``evidence`` and ``telemetry`` on an outcome). It is now a projection of
:mod:`agentic_odi_core.demo`, so the studio and ``odi demo load`` show one study,
labeled ``origin="demo"`` in both.
"""

from __future__ import annotations

from typing import Any

from agentic_odi_core.demo import fixture_rows


def seed_payload() -> dict[str, Any]:
    """Fresh copies of the demo study, as plain records for the prototype canvas."""
    return {name: [row.model_dump() for row in rows] for name, rows in fixture_rows().items()}
