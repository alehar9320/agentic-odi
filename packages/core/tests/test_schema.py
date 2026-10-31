from agentic_odi_core import odi_schema


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
