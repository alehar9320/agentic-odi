from __future__ import annotations

import pytest
from agentic_odi_core.models import Job, create_job
from pydantic import ValidationError


def test_a_well_formed_job_is_accepted() -> None:
    job = Job(name="Onboard customers", description="Reduce time to first value")

    assert job.name == "Onboard customers"


def test_name_accepts_the_length_boundaries() -> None:
    assert Job(name="A B").name == "A B"
    assert Job(name="x" * 64).name == "x" * 64


def test_short_names_are_rejected() -> None:
    with pytest.raises(ValidationError, match="at least 3 characters"):
        Job(name="Jo")


def test_long_names_are_rejected() -> None:
    with pytest.raises(ValidationError, match="at most 64 characters"):
        Job(name="x" * 65)


def test_names_with_punctuation_are_rejected() -> None:
    with pytest.raises(ValidationError, match="String should match pattern"):
        Job(name="Job 1.1")


def test_description_longer_than_500_characters_is_rejected() -> None:
    with pytest.raises(ValidationError, match="at most 500 characters"):
        Job(name="Onboard customers", description="x" * 501)


def test_description_at_the_limit_is_accepted() -> None:
    job = Job(name="Onboard customers", description="x" * 500)

    assert job.description is not None
    assert len(job.description) == 500


def test_create_job_returns_a_validated_job() -> None:
    job = create_job("Onboard customers", description="Reduce time to first value")

    assert isinstance(job, Job)
    assert job.name == "Onboard customers"


def test_create_job_rejects_invalid_input() -> None:
    with pytest.raises(ValidationError):
        create_job("Jo")
