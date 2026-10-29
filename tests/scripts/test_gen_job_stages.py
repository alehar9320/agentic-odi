"""The Studio's eight job stages are generated from the core constant (issue #79)."""

from __future__ import annotations

import gen_job_stages
from agentic_odi_core import job_stage_catalog


def test_committed_typescript_is_not_stale() -> None:
    assert gen_job_stages.main(["--check"]) == 0


def test_every_core_stage_is_rendered_in_order() -> None:
    body = gen_job_stages.render()
    rows = [line for line in body.splitlines() if line.startswith("  { id:")]
    expected = [
        f'  {{ id: "{stage["id"]}", name: "{stage["name"]}", desc: "{stage["desc"]}" }},'
        for stage in job_stage_catalog()
    ]
    assert rows == expected
