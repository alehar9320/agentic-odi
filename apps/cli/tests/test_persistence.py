"""Acceptance test: every ODI entity survives a fresh repository."""

from __future__ import annotations

from agentic_odi_cli.backend import LocalBackend
from agentic_odi_core.sqlite_repository import SQLiteRepository


def test_every_entity_type_survives_reopen(tmp_path):
    db = str(tmp_path / "odi.db")
    backend = LocalBackend(db_path=db)

    job_id = backend.call("add_job", {"name": "J", "description": "d"})["id"]
    # An outcome must exist before steps can be added.
    backend.call(
        "add_outcome",
        {
            "job_id": job_id,
            "statement": "Minimize the time it takes to deploy when releasing",
            "importance": 8.0,
            "satisfaction": 4.0,
        },
    )
    step_id = backend.call("add_step", {"job_id": job_id, "name": "S", "order": 1})["id"]
    outcome = backend.call(
        "add_outcome",
        {
            "job_id": job_id,
            "statement": "Minimize the hours lost to setup when onboarding",
            "importance": 8.0,
            "satisfaction": 4.0,
            "step_id": step_id,
        },
    )
    backend.call(
        "add_customer_outcome",
        {
            "job_id": job_id,
            "customer_value": {
                "direction": "minimize",
                "unit_of_measure": "time",
                "object_of_control": "x",
                "statement": "Min x",
                "importance": 8.0,
                "satisfaction": 4.0,
                "value_metrics": [
                    {
                        "name": "m",
                        "direction": "minimize",
                        "unit_of_measure": "s",
                        "importance": 6.0,
                        "satisfaction": 2.0,
                    }
                ],
            },
            "business_value": {"category": "cost_reduction", "statement": "Save"},
        },
    )
    backend.call(
        "add_evidence",
        {
            "source_name": "gong",
            "source_kind": "mcp",
            "item_type": "resource",
            "name": "feedback",
            "content": "Slow setup",
            "job_id": job_id,
            "step_id": step_id,
            "outcome_id": outcome["id"],
        },
    )

    repo = SQLiteRepository(db_path=db)
    assert repo.get_job(job_id).name == "J"  # type: ignore[union-attr]
    assert repo.get_step(step_id).order == 1  # type: ignore[union-attr]
    stored_outcome = repo.get_outcome(outcome["id"])
    assert stored_outcome is not None and stored_outcome.opportunity_score == 12.0
    customer_outcome = repo.list_customer_outcomes(job_id)[0]
    assert customer_outcome.customer_value.value_metrics[0].opportunity_score == 10.0
    evidence = repo.list_evidence(job_id=job_id)[0]
    assert evidence.step_id == step_id
    assert evidence.outcome_id == outcome["id"]
