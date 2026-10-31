"""The prototype canvas is the demo workspace, not a parallel copy of it.

`seed.py` started life as hand-typed prototype data with keys the model does not
have. `odi demo load` is now the one study, so the canvas has to draw from it:
same rows, same ids, same labels, and no invented fields.
"""

from __future__ import annotations

from agentic_odi_core.demo import DEMO_JOB_ID, FIXTURE_COUNTS
from agentic_odi_core.models import Evidence, Job, Outcome, Step
from agentic_odi_studio_api.studio.seed import seed_payload

_MODEL_FIELDS = {
    "jobs": set(Job.model_fields),
    "steps": set(Step.model_fields),
    "outcomes": set(Outcome.model_fields),
    "evidence": set(Evidence.model_fields),
}


def test_the_seed_canvas_is_the_demo_workspace() -> None:
    payload = seed_payload()

    assert [job["id"] for job in payload["jobs"]] == [DEMO_JOB_ID]
    assert {name: len(rows) for name, rows in payload.items()} == FIXTURE_COUNTS


def test_no_seed_row_invents_a_field_the_model_does_not_have() -> None:
    payload = seed_payload()

    for name, rows in payload.items():
        for row in rows:
            unknown = set(row) - _MODEL_FIELDS[name]
            assert not unknown, f"{name} row {row.get('id')} carries {sorted(unknown)}"


def test_every_seed_row_is_labeled_a_demo() -> None:
    payload = seed_payload()

    rows = [row for rows in payload.values() for row in rows]
    assert rows, "the seed shipped empty"
    assert all(row["origin"] == "demo" for row in rows)


def test_the_seed_steps_are_staged_in_job_map_order() -> None:
    steps = seed_payload()["steps"]

    assert [step["stage"] for step in steps] == [
        "define",
        "locate",
        "prepare",
        "confirm",
        "execute",
        "monitor",
        "modify",
        "conclude",
    ]
