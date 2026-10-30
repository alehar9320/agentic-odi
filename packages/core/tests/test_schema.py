from agentic_odi_core import odi_schema, stage_catalog
from agentic_odi_core.models import JOB_STAGE_ORDER


def test_schema_exposes_every_odi_entity() -> None:
    schema = odi_schema()

    assert {
        "Job",
        "Step",
        "Outcome",
        "ValueMetric",
        "CustomerValue",
        "BusinessValue",
        "CustomerOutcome",
        "Evidence",
        "V2MOM",
    } <= set(schema)


def test_schema_is_json_schema_shaped() -> None:
    job_schema = odi_schema()["Job"]

    assert job_schema["type"] == "object"
    assert "name" in job_schema["properties"]
    assert "id" in job_schema["properties"]


def test_stage_catalog_lists_the_canonical_eight_in_order() -> None:
    catalog = stage_catalog()

    assert [entry["id"] for entry in catalog] == [stage.value for stage in JOB_STAGE_ORDER]
    assert catalog[0] == {
        "id": "define",
        "name": "1. Define",
        "description": "Determine goals and criteria",
    }
    assert catalog[-1]["id"] == "conclude"


def test_stage_catalog_carries_display_copy_for_every_stage() -> None:
    for entry in stage_catalog():
        assert entry["name"], "every stage needs a display name"
        assert entry["description"], "every stage needs a one-line description"
